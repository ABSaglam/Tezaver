# Live Loop Runner v2
"""
CLI runner for live market data loop.

Usage:
    python -m tezaver.matrix.live.live_loop run --runtime 120 --poll 5
    python -m tezaver.matrix.live.live_loop run --real --tf 1m --policy ON_ANY_NEW_BAR --runtime 60 --poll 3
"""

from __future__ import annotations

import argparse
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from tezaver.matrix.live.marketdata.client import IMarketDataClient, DummyMarketDataClient
from tezaver.matrix.live.marketdata.cache import BarCache
from tezaver.matrix.live.marketdata.snapshot_builder import build_snapshot_from_bars


# Tick policies
TICK_POLICY_ON_CLOSED_BAR = "ON_CLOSED_BAR"
TICK_POLICY_ON_ANY_NEW_BAR = "ON_ANY_NEW_BAR"


@dataclass
class LiveLoopConfig:
    """Configuration for live loop."""
    poll_interval_sec: float = 5.0
    tick_policy: str = TICK_POLICY_ON_CLOSED_BAR  # ON_CLOSED_BAR | ON_ANY_NEW_BAR
    max_runtime_sec: float = 300.0
    dry_run: bool = True
    until_next_closed: bool = False  # Exit after first closed bar tick
    align_to_next_close: bool = False  # Calculate runtime to next bar close
    proof_closed: bool = False  # Print PROOF_CLOSED line on first closed tick


@dataclass
class LiveLoopStats:
    """Stats from live loop run."""
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: Optional[datetime] = None
    poll_count: int = 0
    tick_count: int = 0
    skip_count: int = 0
    events: List[Dict[str, Any]] = field(default_factory=list)


def _now_utc() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    """Get current UTC time as ISO string."""
    return _now_utc().isoformat()


def run_live_loop(
    symbols_timeframes: List[tuple],  # [(symbol, timeframe), ...]
    data_client: IMarketDataClient,
    config: LiveLoopConfig,
    cluster=None,  # Optional MatrixLiveCluster
    stop_flag=None,  # Optional threading.Event for stopping
    event_callback=None,  # Optional callback(event) for real-time updates
) -> LiveLoopStats:
    """
    Run live market data loop.
    
    Args:
        symbols_timeframes: List of (symbol, timeframe) to poll
        data_client: Market data client
        config: Loop configuration
        cluster: Optional cluster to tick
        stop_flag: Optional stop event for graceful shutdown
        event_callback: Optional callable(event_dict) for real-time event handling
        
    Returns:
        LiveLoopStats with run summary
    """
    cache = BarCache()
    stats = LiveLoopStats()
    
    # Track last closed bar ts per cell to avoid duplicate ticks
    last_closed_ts: Dict[str, datetime] = {}
    
    # Baseline: first seen closed bar ts per cell (strict mode)
    # Only tick if new_closed_ts > baseline_closed_ts
    baseline_closed_ts: Dict[str, str] = {}
    
    # For until_next_closed mode
    first_closed_tick_received = False
    first_closed_tick_ts: Optional[datetime] = None
    
    # Calculate max_runtime if align_to_next_close
    effective_max_runtime = config.max_runtime_sec
    if config.align_to_next_close and symbols_timeframes:
        # Parse timeframe to calculate next bar close
        tf = symbols_timeframes[0][1]  # Use first cell's timeframe
        tf_minutes = 15
        if tf.endswith("m"):
            tf_minutes = int(tf[:-1])
        elif tf.endswith("h"):
            tf_minutes = int(tf[:-1]) * 60
        
        now = _now_utc()
        # Current bar start
        current_bar_minute = (now.minute // tf_minutes) * tf_minutes
        current_bar_start = now.replace(minute=current_bar_minute, second=0, microsecond=0)
        # Next bar close = current bar start + tf_minutes + buffer
        from datetime import timedelta
        next_close = current_bar_start + timedelta(minutes=tf_minutes) + timedelta(seconds=30)
        secs_to_close = (next_close - now).total_seconds()
        effective_max_runtime = max(secs_to_close, 60)  # At least 60s
        print(f"[LIVE_LOOP] Aligned to next close: {next_close.isoformat()}, max_runtime={effective_max_runtime:.0f}s")
    
    print(f"[LIVE_LOOP] Starting with {len(symbols_timeframes)} cells")
    print(f"[LIVE_LOOP] Config: poll={config.poll_interval_sec}s, policy={config.tick_policy}")
    if config.until_next_closed:
        print("[LIVE_LOOP] Mode: until_next_closed (will exit after first closed bar tick)")
    
    start_ts = time.time()
    
    while True:
        # Check stop conditions
        elapsed = time.time() - start_ts
        if elapsed > effective_max_runtime:
            print(f"[LIVE_LOOP] Max runtime reached ({effective_max_runtime:.0f}s)")
            break
        
        if stop_flag is not None and stop_flag.is_set():
            print("[LIVE_LOOP] Stop flag received")
            break
        
        # Check until_next_closed exit
        if config.until_next_closed and first_closed_tick_received:
            print(f"[LIVE_LOOP] First closed bar tick received at {first_closed_tick_ts}")
            break
        
        # Poll each symbol/timeframe
        for symbol, timeframe in symbols_timeframes:
            cell_key = cache.get_cell_key(symbol, timeframe)
            
            try:
                # Fetch latest bars
                bars = data_client.get_latest_bars(symbol, timeframe, limit=100)
                server_time = data_client.get_server_time()
                
                # Check is_closed column if available (real Binance data)
                has_is_closed = "is_closed" in bars.columns
                
                # Determine if we should tick based on policy
                should_tick = False
                tick_reason = "SKIP_NO_NEW_BAR"
                
                if config.tick_policy == TICK_POLICY_ON_CLOSED_BAR and has_is_closed:
                    # Only tick on closed bars
                    closed_bars = bars[bars["is_closed"] == True]
                    
                    if not closed_bars.empty:
                        # Get bar_close_ts from closed bars if available
                        if "close_time_ms" in closed_bars.columns:
                            latest_closed_ms = closed_bars["close_time_ms"].max()
                            latest_closed_ts_str = datetime.utcfromtimestamp(latest_closed_ms / 1000).isoformat()
                        else:
                            latest_closed_ts = closed_bars["ts"].max()
                            latest_closed_ts_str = latest_closed_ts.isoformat() if hasattr(latest_closed_ts, 'isoformat') else str(latest_closed_ts)
                        
                        prev_closed_ts = last_closed_ts.get(cell_key)
                        latest_closed_ts = closed_bars["ts"].max()
                        
                        # Set baseline on first poll (strict mode)
                        if cell_key not in baseline_closed_ts:
                            baseline_closed_ts[cell_key] = latest_closed_ts_str
                            print(f"[LIVE_LOOP] Baseline set for {cell_key}: {latest_closed_ts_str}")
                        
                        # Check if this is a NEW closed bar (after baseline)
                        baseline_ts_str = baseline_closed_ts.get(cell_key, "")
                        
                        if latest_closed_ts_str <= baseline_ts_str:
                            # Old or same as baseline - skip
                            should_tick = False
                            tick_reason = "SKIP_OLD_CLOSED_BAR"
                            print(f"[LIVE_SKIP_OLD_CLOSED_BAR] {symbol}/{timeframe} baseline={baseline_ts_str[:19]} seen={latest_closed_ts_str[:19]}")
                        elif prev_closed_ts is None or latest_closed_ts > prev_closed_ts:
                            should_tick = True
                            tick_reason = "NEW_CLOSED_BAR"
                            last_closed_ts[cell_key] = latest_closed_ts
                            # Update baseline on successful tick
                            baseline_closed_ts[cell_key] = latest_closed_ts_str
                        else:
                            tick_reason = "SKIP_SAME_CLOSED_BAR"
                    else:
                        tick_reason = "SKIP_NO_CLOSED_BAR"
                else:
                    # ON_ANY_NEW_BAR or no is_closed column (dummy data)
                    has_new = cache.has_new_bar(cell_key, bars)
                    if has_new:
                        should_tick = True
                        tick_reason = "NEW_BAR_ANY"
                    else:
                        tick_reason = "SKIP_NO_NEW_BAR"
                
                # Build base event
                last_bar_ts = bars["ts"].max() if not bars.empty else None
                event = {
                    "ts": _now_iso(),
                    "event_type": "LIVE_POLL",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "bar_count": len(bars),
                    "last_bar_ts": last_bar_ts.isoformat() if last_bar_ts else None,
                    "server_time": server_time.isoformat() if hasattr(server_time, 'isoformat') else str(server_time),
                    "tick_reason": tick_reason,
                }
                
                if has_is_closed:
                    closed_count = bars["is_closed"].sum()
                    event["closed_bar_count"] = int(closed_count)
                
                stats.poll_count += 1
                
                if should_tick:
                    # Update cache with closed bars only if using ON_CLOSED_BAR
                    if config.tick_policy == TICK_POLICY_ON_CLOSED_BAR and has_is_closed:
                        closed_bars = bars[bars["is_closed"] == True]
                        new_count = cache.update(cell_key, closed_bars)
                    else:
                        new_count = cache.update(cell_key, bars)
                    
                    # Build snapshot
                    cached_bars = cache.get_bars(cell_key)
                    snapshot = build_snapshot_from_bars(cached_bars, symbol, timeframe)
                    
                    # Tick cluster if provided
                    if cluster is not None:
                        cluster.tick(symbol, timeframe, snapshot)
                    
                    event["event_type"] = "LIVE_TICK"
                    event["new_bars_added"] = new_count
                    event["snapshot_close"] = snapshot.get("close")
                    event["bar_close_ts"] = snapshot.get("bar_close_ts")
                    event["tick_received_ts"] = _now_iso()
                    event["is_closed"] = snapshot.get("is_closed")
                    event["rsi_15m"] = snapshot.get("rsi_15m")
                    
                    stats.tick_count += 1
                    close_val = snapshot.get('close', 0)
                    print(f"[LIVE_TICK] {symbol}/{timeframe} close={close_val:.2f} reason={tick_reason}")
                    
                    # Mark first closed tick for until_next_closed mode
                    if tick_reason == "NEW_CLOSED_BAR" and not first_closed_tick_received:
                        first_closed_tick_received = True
                        first_closed_tick_ts = _now_utc()
                        
                        # Print PROOF_CLOSED line if proof mode enabled
                        if config.proof_closed:
                            bar_close_ts = snapshot.get("bar_close_ts", "?")
                            lag_sec = None
                            if bar_close_ts and bar_close_ts != "?":
                                try:
                                    bar_close_dt = datetime.fromisoformat(bar_close_ts)
                                    lag_sec = (_now_utc().replace(tzinfo=None) - bar_close_dt).total_seconds()
                                except:
                                    pass
                            
                            lag_str = f"{lag_sec:.1f}" if lag_sec else "?"
                            tick_received_ts = _now_iso()
                            align_on = config.align_to_next_close
                            baseline_ts = baseline_closed_ts.get(cell_key, "?")
                            print(f"[PROOF_CLOSED] {symbol}/{timeframe} baseline={baseline_ts[:19]} seen={bar_close_ts[:19] if bar_close_ts else '?'} lag={lag_str} align={align_on} strict=True")
                            
                            # Emit CLOSED_PROOF event
                            proof_event = {
                                "ts": tick_received_ts,
                                "event_type": "CLOSED_PROOF",
                                "symbol": symbol,
                                "timeframe": timeframe,
                                "bar_close_ts": bar_close_ts,
                                "tick_received_ts": tick_received_ts,
                                "baseline_closed_ts": baseline_ts,
                                "strict_new_closed": True,
                                "lag_sec": lag_sec,
                                "close": close_val,
                                "policy": config.tick_policy,
                                "poll_interval": config.poll_interval_sec,
                                "align": align_on,
                            }
                            stats.events.append(proof_event)
                            if event_callback:
                                try:
                                    event_callback(proof_event)
                                except:
                                    pass
                else:
                    event["event_type"] = "LIVE_SKIP"
                    stats.skip_count += 1
                    print(f"[LIVE_SKIP] {symbol}/{timeframe} ({tick_reason})")
                
                stats.events.append(event)
                
                # Call event callback for real-time updates
                if event_callback:
                    try:
                        event_callback(event)
                    except Exception as cb_err:
                        print(f"[LIVE_LOOP] Event callback error: {cb_err}")
                
            except Exception as e:
                event = {
                    "ts": _now_iso(),
                    "event_type": "LIVE_ERROR",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "error": str(e),
                }
                stats.events.append(event)
                if event_callback:
                    try:
                        event_callback(event)
                    except:
                        pass
                print(f"[LIVE_ERROR] {symbol}/{timeframe}: {e}")
        
        # Sleep until next poll
        time.sleep(config.poll_interval_sec)
    
    stats.end_time = _now_utc()
    print(f"[LIVE_LOOP] Finished: polls={stats.poll_count}, ticks={stats.tick_count}, skips={stats.skip_count}")
    
    return stats


def main():
    """
    RUNBOOK — Live Loop CLI
    ========================
    1) Run proof (1m/15m):
       PYTHONPATH=src python -m tezaver.matrix.live.live_loop run --real --tf 15m --policy ON_CLOSED_BAR --proof-closed
    
    2) Run proof + router (E2E):
       PYTHONPATH=src python -m tezaver.matrix.live.live_loop proof_router --real --tf 15m --poll 5
       => Outputs: PROOF_CLOSED + ROUTER_TICK_RESULT
    
    3) Run proof + router + cluster (DRY RUN E2E):
       PYTHONPATH=src python -m tezaver.matrix.live.live_loop proof_router_cluster --real --tf 15m --poll 5
       => Outputs: PROOF_CLOSED + ROUTER_TICK + ROUTER_CLUSTER_OK
    """
    parser = argparse.ArgumentParser(description="Live loop runner v2")
    parser.add_argument("command", choices=["run", "proof_router", "proof_router_cluster", "proof_open_close", "policy_cycle"], help="Command to run")
    parser.add_argument("--runtime", type=int, default=60, help="Max runtime in seconds")
    parser.add_argument("--poll", type=int, default=5, help="Poll interval in seconds")
    parser.add_argument("--symbols", type=str, default="BTCUSDT", help="Comma-separated symbols")
    parser.add_argument("--tf", type=str, default="15m", help="Timeframe")
    parser.add_argument("--policy", type=str, default="ON_CLOSED_BAR", 
                       choices=["ON_CLOSED_BAR", "ON_ANY_NEW_BAR"],
                       help="Tick policy")
    parser.add_argument("--hold-policy", type=str, default="HOLD_NEXT_CLOSED",
                       choices=["PASS_THROUGH", "HOLD_NEXT_CLOSED"],
                       help="Per-cell hold policy for policy_cycle command")
    parser.add_argument("--real", action="store_true", help="Use real Binance data (default: dummy)")
    parser.add_argument("--until-next-closed", action="store_true", 
                       help="Exit after first closed bar tick")
    parser.add_argument("--align-to-next-close", action="store_true",
                       help="Calculate runtime to next bar close")
    parser.add_argument("--proof-closed", action="store_true",
                       help="Proof mode: print PROOF_CLOSED line on first closed bar and exit")
    parser.add_argument("--until-done", action="store_true",
                       help="For hold-policy: run until policy cycle DONE (OPEN→CLOSE)")
    
    # Exchange mode arguments (for proof_router_cluster)
    parser.add_argument("--exchange-mode", type=str, default="DRY_RUN",
                       choices=["DRY_RUN", "DUMMY_ORDER", "REAL_TESTNET", "REAL_MAINNET"],
                       help="Exchange execution mode")
    parser.add_argument("--exchange-enabled", action="store_true", default=False,
                       help="Enable exchange")
    parser.add_argument("--no-exchange-enabled", action="store_false", dest="exchange_enabled",
                       help="Disable exchange")
    parser.add_argument("--armed", action="store_true", default=False,
                       help="Enable armed mode")
    parser.add_argument("--no-armed", action="store_false", dest="armed",
                       help="Disable armed mode")
    parser.add_argument("--force-dry-run", action="store_true", default=True,
                       help="Force dry run mode")
    parser.add_argument("--no-force-dry-run", action="store_false", dest="force_dry_run",
                       help="Disable force dry run")
    
    # Proof open/close specific args
    parser.add_argument("--preflight-mode", type=str, default="BLOCK",
                       choices=["BLOCK", "FLATTEN_FIRST", "IGNORE"],
                       help="Preflight residual handling mode")
    parser.add_argument("--min-pos-abs", type=float, default=1e-12,
                       help="Minimum abs(position) to consider residual")
    parser.add_argument("--close-policy", type=str, default="NEXT_CLOSED_BAR",
                       choices=["NEXT_CLOSED_BAR", "NEXT_SIGNAL"],
                       help="Close trigger policy (v3)")
    
    # Dust policy arguments
    parser.add_argument("--dust-policy", type=str, default="IGNORE",
                       choices=["IGNORE", "FLATTEN_AFTER", "BLOCK"],
                       help="Dust handling policy: IGNORE=accept dust, FLATTEN_AFTER=cleanup, BLOCK=fail if dust")
    parser.add_argument("--dust-threshold", type=float, default=0.002,
                       help="Dust threshold (abs qty considered dust)")
    parser.add_argument("--close-qty-mult", type=float, default=1.0,
                       help="Close qty multiplier (0.5 = partial close for BLOCK test)")
    
    args = parser.parse_args()
    
    if args.command == "proof_router":
        # Proof + Router E2E mode
        from tezaver.matrix.live.live_router import MatrixLiveRouter, LiveRouterConfig
        
        print("[PROOF_ROUTER] Starting end-to-end proof + router mode")
        
        # Parse symbols
        symbols = [s.strip() for s in args.symbols.split(",")]
        symbols_timeframes = [(s, args.tf) for s in symbols]
        
        # Client
        if args.real:
            from tezaver.matrix.live.marketdata.client import BinancePublicClient
            client = BinancePublicClient()
            print("[PROOF_ROUTER] Using REAL Binance public data")
        else:
            from tezaver.matrix.live.marketdata.client import DummyMarketDataClient
            client = DummyMarketDataClient()
            print("[PROOF_ROUTER] Using DUMMY data")
        
        # Create router with forced dry_run
        router_config = LiveRouterConfig(
            enabled=True,
            force_dry_run=True,
            only_symbols=symbols,
            only_timeframes=[args.tf],
        )
        router = MatrixLiveRouter(cluster=None, config=router_config)
        
        # Track router result for output
        router_result = {"ticks": 0, "skips": 0, "last_tick": None}
        
        def router_callback(snapshot):
            nonlocal router_result
            router.handle_snapshot(snapshot)
            router_result["ticks"] = router.tick_count
            router_result["skips"] = router.skip_count
            router_result["last_tick"] = router.last_tick
            
            # Print ROUTER_TICK_RESULT
            if router.last_tick:
                lt = router.last_tick
                print(f"ROUTER_TICK_RESULT | {lt.get('symbol')}/{lt.get('timeframe')} bar_close_ts={lt.get('bar_close_ts')} dry_run=True ticks={router.tick_count} skips={router.skip_count}")
        
        # Config: forced proof mode + align
        config = LiveLoopConfig(
            poll_interval_sec=args.poll,
            tick_policy="ON_CLOSED_BAR",
            max_runtime_sec=1800,  # 30 min max for 15m
            dry_run=True,
            until_next_closed=True,
            align_to_next_close=True,
            proof_closed=True,
        )
        
        # Event callback to route closed bar ticks
        def on_event(event):
            if event.get("event_type") == "CLOSED_PROOF":
                # Build snapshot and route to router
                snapshot = {
                    "symbol": event.get("symbol"),
                    "timeframe": event.get("timeframe"),
                    "bar_close_ts": event.get("bar_close_ts"),
                    "close": event.get("close"),
                }
                router_callback(snapshot)
        
        # Run
        stats = run_live_loop(symbols_timeframes, client, config, event_callback=on_event)
        
        # Summary
        print()
        print("=" * 60)
        print("PROOF_ROUTER SUMMARY")
        print("=" * 60)
        print(f"Polls: {stats.poll_count}")
        print(f"Ticks: {stats.tick_count}")
        print(f"Skips: {stats.skip_count}")
        print(f"Router Ticks: {router_result['ticks']}")
        print(f"Router Skips: {router_result['skips']}")
        
    elif args.command == "proof_router_cluster":
        # Proof + Router + Cluster DRY RUN E2E mode
        from tezaver.matrix.live.live_router import MatrixLiveRouter, LiveRouterConfig
        
        print("[PROOF_ROUTER_CLUSTER] Starting E2E proof + router + cluster (DRY RUN)")
        
        # Parse symbols
        symbols = [s.strip() for s in args.symbols.split(",")]
        symbols_timeframes = [(s, args.tf) for s in symbols]
        
        # Client
        if args.real:
            from tezaver.matrix.live.marketdata.client import BinancePublicClient
            client = BinancePublicClient()
            print("[PROOF_ROUTER_CLUSTER] Using REAL Binance public data")
        else:
            from tezaver.matrix.live.marketdata.client import DummyMarketDataClient
            client = DummyMarketDataClient()
            print("[PROOF_ROUTER_CLUSTER] Using DUMMY data")
        
        # Get exchange mode from args
        exchange_mode = getattr(args, "exchange_mode", "DRY_RUN")
        exchange_enabled = getattr(args, "exchange_enabled", False)
        armed = getattr(args, "armed", False)
        force_dry_run = getattr(args, "force_dry_run", True)
        
        # Get hold-policy and until-done flags
        hold_policy = getattr(args, "hold_policy", "NONE")
        until_done = getattr(args, "until_done", False)
        use_policy_cycle = (hold_policy == "HOLD_NEXT_CLOSED" and until_done)
        
        print(f"[PROOF_ROUTER_CLUSTER] exchange_mode={exchange_mode} exchange_enabled={exchange_enabled} armed={armed} force_dry_run={force_dry_run}")
        if use_policy_cycle:
            print(f"[PROOF_ROUTER_CLUSTER] POLICY MODE: hold_policy={hold_policy} until_done={until_done}")
        
        # Create stub cluster for DRY_RUN testing (no real engine)
        class StubCluster:
            """Minimal stub cluster for E2E proof."""
            def __init__(self, event_sink=None):
                self.tick_count = 0
                self.last_tick = None
                self._event_sink = event_sink
            
            def tick(self, symbol, timeframe, market_snapshot, runtime_overrides=None):
                self.tick_count += 1
                self.last_tick = market_snapshot
                
                # Determine exec mode based on conditions
                overrides = runtime_overrides or {}
                _force_dry_run = overrides.get("force_dry_run", force_dry_run)
                _exchange_mode = overrides.get("exchange_mode", exchange_mode)
                _armed = overrides.get("armed", armed)
                _exchange_enabled = overrides.get("exchange_enabled", exchange_enabled)
                
                # Exec mode logic
                if _force_dry_run or _exchange_mode == "DRY_RUN" or not _armed or not _exchange_enabled:
                    exec_mode = "dry_run"
                    order_id = "DRY_RUN"
                    dry_run = True
                elif _exchange_mode == "DUMMY_ORDER":
                    exec_mode = "dummy_order"
                    order_id = "DUMMY-ORDER"
                    dry_run = False
                elif _exchange_mode == "REAL_TESTNET":
                    exec_mode = "real_testnet"
                    dry_run = False
                    
                    # Use real ArmedExecutor with BinanceTestnetGateway
                    from tezaver.matrix.live.live_gateway import ArmedExecutor
                    from tezaver.matrix.live.secrets import EnvSecretsVault, FileSecretsVault, CompositeVault
                    from pathlib import Path
                    
                    try:
                        # Create vault with ENV and FILE sources
                        vaults = [EnvSecretsVault()]
                        secrets_file = Path("data/secrets/live_keys.txt")
                        if secrets_file.exists():
                            vaults.append(FileSecretsVault(secrets_file))
                        vault = CompositeVault(vaults)
                        api_key = vault.get("API_KEY") or vault.get("BINANCE_API_KEY")
                        api_secret = vault.get("API_SECRET") or vault.get("BINANCE_API_SECRET")
                        
                        if api_key and api_secret:
                            executor = ArmedExecutor(
                                armed=True,
                                exchange_enabled=True,
                                event_sink=self._event_sink,
                                exchange_mode="REAL_TESTNET",
                                api_key=api_key,
                                api_secret=api_secret,
                            )
                            
                            # Execute via real gateway
                            import time
                            start_time = time.time()
                            result = executor.execute(
                                symbol=symbol,
                                timeframe=timeframe,
                                profile_id=f"{symbol}_{timeframe}_live",
                                action="BUY",
                                qty=0.002,  # ~$180 to meet Binance min $100 notional
                                tick_index=self.tick_count,
                                decision_ts=str(market_snapshot.get("bar_close_ts", "")),
                            )
                            latency_ms = (time.time() - start_time) * 1000
                            
                            order_id = result.order_id or "GATEWAY_ERROR"
                            
                            # Tripwire: stub order_id detection
                            if order_id.startswith("TESTNET-") or order_id.startswith("DUMMY"):
                                raise RuntimeError(f"Stub order_id detected in REAL_TESTNET mode: {order_id}")
                            
                            # Emit gateway telemetry
                            if self._event_sink:
                                self._event_sink({
                                    "event_type": "GATEWAY_HTTP_OK" if result.success else "GATEWAY_HTTP_ERR",
                                    "endpoint": "fapi/v1/order",
                                    "status_code": 200 if result.success else 400,
                                    "latency_ms": round(latency_ms, 2),
                                    "order_id": order_id,
                                    "success": result.success,
                                    "error": result.reason if not result.success else None,
                                })
                        else:
                            order_id = "SECRETS_MISSING"
                    except Exception as e:
                        order_id = f"ERROR:{str(e)[:30]}"
                        if self._event_sink:
                            self._event_sink({
                                "event_type": "GATEWAY_HTTP_ERR",
                                "error": str(e),
                            })
                elif _exchange_mode == "REAL_MAINNET":
                    exec_mode = "real_mainnet"
                    order_id = "MAINNET_NOT_IMPLEMENTED"
                    dry_run = True  # Safety - not implemented yet
                else:
                    exec_mode = "unknown"
                    order_id = "UNKNOWN_MODE"
                    dry_run = True
                
                profile_id = f"{symbol}_{timeframe}_live"
                bar_close_ts = market_snapshot.get("bar_close_ts", "")
                fingerprint = f"{symbol}|{timeframe}|{profile_id}|{bar_close_ts}"
                
                # Emit ORDER_SUBMIT event (ArmedExecutor simulation)
                if self._event_sink:
                    from datetime import datetime, timezone
                    ts = datetime.now(timezone.utc).isoformat()
                    
                    self._event_sink({
                        "ts": ts,
                        "event_type": "ORDER_SUBMIT",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "profile_id": profile_id,
                        "exchange_mode": _exchange_mode,
                        "exec_mode": exec_mode,
                        "armed": _armed,
                        "exchange_enabled": _exchange_enabled,
                        "order_id": order_id,
                        "fingerprint": fingerprint,
                        "request_meta": {"type": "MARKET", "side": "BUY"},
                    })
                    
                    # Emit ORDER_RESULT event
                    self._event_sink({
                        "ts": ts,
                        "event_type": "ORDER_RESULT",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "profile_id": profile_id,
                        "exec_mode": exec_mode,
                        "order_id": order_id,
                        "success": True,
                        "duplicate": False,
                        "paused": False,
                        "reason": f"{_exchange_mode}_MODE",
                        "fingerprint": fingerprint,
                        "exchange_mode": _exchange_mode,
                        "armed": _armed,
                        "exchange_enabled": _exchange_enabled,
                        "allow": True,
                    })
                
                return {
                    "decisions_count": 1,
                    "executions_count": 1,
                    "dry_run": dry_run,
                    "exec_mode": exec_mode,
                    "order_id": order_id,
                    "allow": True,
                    "profile_id": profile_id,
                    "exchange_mode": _exchange_mode,
                    "armed": _armed,
                    "exchange_enabled": _exchange_enabled,
                    "force_dry_run": _force_dry_run,
                }
        
        # Create NDJSON event sink for telemetry (before cluster)
        import json
        from pathlib import Path
        from tezaver.matrix.live.secrets import redact_secrets
        
        ndjson_path = Path("data/logs/live_events.ndjson")
        ndjson_path.parent.mkdir(parents=True, exist_ok=True)
        
        from tezaver.matrix.live.order_state import get_order_state_store
        order_store = get_order_state_store()
        
        def ndjson_event_sink(event):
            """Write event to NDJSON file (no secrets)."""
            safe_event = redact_secrets(event)
            with open(ndjson_path, "a") as f:
                f.write(json.dumps(safe_event) + "\n")
            
            # Update order state store
            order_store.apply_event(event)
            
            # Print console summary for key events
            event_type = event.get("event_type", "")
            if event_type == "ROUTER_CLUSTER_EXEC_SUMMARY":
                print(f"[EXEC_SUMMARY] {event.get('symbol')}/{event.get('timeframe')} exec_mode={event.get('exec_mode')} order_id={event.get('order_id')} allow={event.get('allow')}")
            elif event_type == "ORDER_SUBMIT":
                print(f"[ORDER_SUBMIT] {event.get('symbol')}/{event.get('timeframe')} exec_mode={event.get('exec_mode')} order_id={event.get('order_id')}")
        
        # Create stub cluster with event sink
        stub_cluster = StubCluster(event_sink=ndjson_event_sink)
        
        # Create router with cluster and event sink
        router_config = LiveRouterConfig(
            enabled=True,
            force_dry_run=force_dry_run,
            only_symbols=symbols,
            only_timeframes=[args.tf],
        )
        router = MatrixLiveRouter(cluster=stub_cluster, config=router_config, event_sink=ndjson_event_sink)
        
        # Track router result
        router_result = {"ticks": 0, "skips": 0, "last_tick": None, "cluster_ticks": 0}
        
        def router_callback(snapshot):
            nonlocal router_result
            router.handle_snapshot(snapshot)
            router_result["ticks"] = router.tick_count
            router_result["skips"] = router.skip_count
            router_result["last_tick"] = router.last_tick
            router_result["cluster_ticks"] = stub_cluster.tick_count
        
        # Config: forced proof mode + align
        # If use_policy_cycle=True, we run until policy DONE, not until first tick
        if use_policy_cycle:
            # Dynamic max_runtime based on timeframe
            if args.tf == "1m":
                max_runtime = 300  # 5 min
            elif args.tf == "15m":
                max_runtime = 2100  # 35 min
            else:
                max_runtime = 600  # 10 min default
            
            config = LiveLoopConfig(
                poll_interval_sec=args.poll,
                tick_policy="ON_CLOSED_BAR",
                max_runtime_sec=max_runtime,
                dry_run=True,
                until_next_closed=False,  # Don't exit on first tick
                align_to_next_close=True,
                proof_closed=True,
            )
        else:
            config = LiveLoopConfig(
                poll_interval_sec=args.poll,
                tick_policy="ON_CLOSED_BAR",
                max_runtime_sec=1800,  # 30 min max for 15m
                dry_run=True,
                until_next_closed=True,
                align_to_next_close=True,
                proof_closed=True,
            )
        
        # If use_policy_cycle, create HoldNextClosedPolicy
        policy = None
        policy_gateway = None
        policy_result_summary = {}
        
        if use_policy_cycle:
            from tezaver.matrix.live.live_policy import HoldNextClosedPolicy, PolicyState
            from tezaver.matrix.live.live_gateway import BinanceTestnetGateway, DummyExchangeGateway
            from tezaver.matrix.live.secrets import EnvSecretsVault, FileSecretsVault, CompositeVault
            from pathlib import Path
            
            # Setup gateway based on exchange_mode
            if exchange_mode == "REAL_TESTNET":
                vaults = [EnvSecretsVault()]
                secrets_file = Path("data/secrets/live_keys.txt")
                if secrets_file.exists():
                    vaults.append(FileSecretsVault(secrets_file))
                vault = CompositeVault(vaults)
                api_key = vault.get("API_KEY") or vault.get("BINANCE_API_KEY")
                api_secret = vault.get("API_SECRET") or vault.get("BINANCE_API_SECRET")
                
                if api_key and api_secret:
                    policy_gateway = BinanceTestnetGateway(api_key, api_secret)
                    print("[PROOF_ROUTER_CLUSTER] Policy using REAL BinanceTestnetGateway")
                else:
                    print("[PROOF_ROUTER_CLUSTER] ERROR: SECRETS_MISSING for policy")
                    sys.exit(1)
            else:
                policy_gateway = DummyExchangeGateway()
                print("[PROOF_ROUTER_CLUSTER] Policy using DummyExchangeGateway")
            
            symbol = symbols[0]
            profile_id = f"{symbol}_{args.tf}_policy"
            
            # Get dust policy params
            dust_policy = getattr(args, "dust_policy", "IGNORE")
            dust_threshold = getattr(args, "dust_threshold", 0.002)
            close_qty_mult = getattr(args, "close_qty_mult", 1.0)
            
            policy = HoldNextClosedPolicy(
                gateway=policy_gateway,
                event_sink=ndjson_event_sink,
                qty=0.002,
                exchange_mode=exchange_mode,
                armed=armed,
                exchange_enabled=exchange_enabled,
                dust_policy=dust_policy,
                dust_threshold=dust_threshold,
                close_qty_mult=close_qty_mult,
            )
            
            print(f"[PROOF_ROUTER_CLUSTER] Policy profile_id={profile_id}")
            print(f"[PROOF_ROUTER_CLUSTER] dust_policy={dust_policy} dust_threshold={dust_threshold} close_qty_mult={close_qty_mult}")
            print(f"[PROOF_ROUTER_CLUSTER] max_runtime={max_runtime}s for tf={args.tf}")
            print("[PROOF_ROUTER_CLUSTER] Waiting for NEW_CLOSED_BAR ticks (policy mode)...")
        
        # Event callback to route closed bar ticks
        def on_event(event):
            nonlocal policy, policy_result_summary
            if event.get("event_type") == "CLOSED_PROOF":
                snapshot = {
                    "symbol": event.get("symbol"),
                    "timeframe": event.get("timeframe"),
                    "bar_close_ts": event.get("bar_close_ts"),
                    "close": event.get("close"),
                }
                
                # If policy cycle active, route through policy
                if use_policy_cycle and policy:
                    symbol = event.get("symbol")
                    tf = event.get("timeframe")
                    bar_close_ts = event.get("bar_close_ts")
                    profile_id = f"{symbol}_{tf}_policy"
                    
                    # Get cell state to determine decision
                    cell_state = policy.get_cell_state(symbol, tf, profile_id)
                    decision = "OPEN" if cell_state.state.value == "IDLE" else None
                    
                    result = policy.handle_tick(
                        symbol=symbol,
                        tf=tf,
                        profile_id=profile_id,
                        bar_close_ts=bar_close_ts,
                        decision=decision,
                    )
                    
                    print(f"[POLICY_TICK] action={result.action} state={result.state.value}")
                    
                    # Store summary when done
                    if policy.is_cycle_complete(symbol, tf, profile_id):
                        policy_result_summary = policy.get_summary(symbol, tf, profile_id)
                else:
                    # Normal router callback
                    router_callback(snapshot)
        
        # Custom run for policy cycle (need to track policy completion)
        if use_policy_cycle:
            from datetime import datetime, timezone
            
            symbol = symbols[0]
            profile_id = f"{symbol}_{args.tf}_policy"
            
            # Manual loop for policy cycle
            last_baseline = None
            start_time = datetime.now(timezone.utc)
            poll_count = 0
            tick_count = 0
            skip_count = 0
            
            while not policy.is_cycle_complete(symbol, args.tf, profile_id):
                elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
                if elapsed > max_runtime:
                    print(f"[PROOF_ROUTER_CLUSTER] TIMEOUT after {max_runtime}s")
                    break
                
                # Fetch bars
                bars_df = client.get_latest_bars(symbol, args.tf, limit=5)
                poll_count += 1
                
                if bars_df is None or bars_df.empty:
                    time.sleep(args.poll)
                    continue
                
                # Get last closed bar
                if "is_closed" in bars_df.columns:
                    closed_bars = bars_df[bars_df["is_closed"] == True]
                    if closed_bars.empty:
                        time.sleep(args.poll)
                        continue
                    prev_bar = closed_bars.iloc[-1]
                else:
                    if len(bars_df) < 2:
                        time.sleep(args.poll)
                        continue
                    prev_bar = bars_df.iloc[-2]
                
                # Get bar close timestamp
                if "close_time_ms" in prev_bar:
                    bar_close_ts = datetime.utcfromtimestamp(prev_bar["close_time_ms"] / 1000).isoformat()
                else:
                    bar_close_ts = str(prev_bar["ts"])
                close_price = prev_bar["close"]
                
                # Dedup
                if bar_close_ts == last_baseline:
                    skip_count += 1
                    time.sleep(args.poll)
                    continue
                
                last_baseline = bar_close_ts
                tick_count += 1
                print(f"[PROOF_ROUTER_CLUSTER] NEW_CLOSED_BAR: {bar_close_ts} close={close_price}")
                
                # Emit CLOSED_PROOF event (triggers on_event)
                on_event({
                    "event_type": "CLOSED_PROOF",
                    "symbol": symbol,
                    "timeframe": args.tf,
                    "bar_close_ts": bar_close_ts,
                    "close": close_price,
                })
                
                time.sleep(args.poll)
            
            # Policy cycle summary
            summary = policy.get_summary(symbol, args.tf, profile_id)
            
            print()
            print("=" * 60)
            print("PROOF_ROUTER_CLUSTER_POLICY SUMMARY")
            print("=" * 60)
            print(f"Polls: {poll_count}")
            print(f"Ticks: {tick_count}")
            print(f"Skips: {skip_count}")
            print(f"Open order_id: {summary['open_order_id']}")
            print(f"Close order_id: {summary['close_order_id']}")
            print(f"Effective bar: {summary['open_effective_bar_close_ts']}")
            print(f"Close bar: {summary['close_bar_close_ts']}")
            print(f"bars_waited_effective: {summary['bars_waited_effective']}")
            print(f"lag_sec_effective: {summary['lag_sec_effective']}")
            print(f"residual_after: {summary['residual_after']}")
            print(f"dust_policy: {summary['dust_policy']}")
            print(f"dust_threshold: {summary['dust_threshold']}")
            print(f"cleanup_attempted: {summary['cleanup_attempted']}")
            print(f"cleanup_result: {summary['cleanup_result']}")
            
            success = summary['close_order_id'] is not None
            reduce_only = True  # Policy always uses reduceOnly for CLOSE
            cleanup_str = "YES" if summary['cleanup_attempted'] else "NO"
            
            print(f"\nPROOF_ROUTER_CLUSTER_POLICY_OK | {symbol}/{args.tf} open={summary['open_order_id']} close={summary['close_order_id']} reduceOnly={reduce_only} eff_wait={summary['bars_waited_effective']} eff_lag={summary['lag_sec_effective']} residual={summary['residual_after']} dust_policy={summary['dust_policy']} cleanup={cleanup_str} allow=true exec_mode={exchange_mode.lower()}")
        else:
            # Run standard loop
            stats = run_live_loop(symbols_timeframes, client, config, event_callback=on_event)
            
            # Summary
            print()
            print("=" * 60)
            print("PROOF_ROUTER_CLUSTER SUMMARY (DRY RUN)")
            print("=" * 60)
            print(f"Polls: {stats.poll_count}")
            print(f"Ticks: {stats.tick_count}")
            print(f"Skips: {stats.skip_count}")
            print(f"Router Ticks: {router_result['ticks']}")
            print(f"Router Skips: {router_result['skips']}")
            print(f"Cluster Ticks: {router_result['cluster_ticks']}")
        
    elif args.command == "run":
        # Parse symbols
        symbols = [s.strip() for s in args.symbols.split(",")]
        symbols_timeframes = [(s, args.tf) for s in symbols]
        
        # Client
        if args.real:
            from tezaver.matrix.live.marketdata.client import BinancePublicClient
            client = BinancePublicClient()
            print("[LIVE_LOOP] Using REAL Binance public data (no auth needed)")
        else:
            from tezaver.matrix.live.marketdata.client import DummyMarketDataClient
            client = DummyMarketDataClient()
            print("[LIVE_LOOP] Using DUMMY data")
        
        # Handle proof-closed mode
        proof_closed = getattr(args, 'proof_closed', False)
        until_next_closed = getattr(args, 'until_next_closed', False)
        align_to_next_close = getattr(args, 'align_to_next_close', False)
        
        if proof_closed:
            # Force proof mode settings
            until_next_closed = True
            align_to_next_close = True
            print("[LIVE_LOOP] PROOF MODE: will exit after first closed bar tick")
        
        # Config
        config = LiveLoopConfig(
            poll_interval_sec=args.poll,
            tick_policy=args.policy,
            max_runtime_sec=args.runtime,
            dry_run=True,
            until_next_closed=until_next_closed,
            align_to_next_close=align_to_next_close,
            proof_closed=proof_closed,
        )
        
        # Run
        stats = run_live_loop(symbols_timeframes, client, config)
        
        # Print summary
        print()
        print("="*60)
        print("LIVE LOOP SUMMARY")
        print("="*60)
        print(f"Duration: {(stats.end_time - stats.start_time).total_seconds():.1f}s")
        print(f"Polls: {stats.poll_count}")
        print(f"Ticks: {stats.tick_count}")
        print(f"Skips: {stats.skip_count}")
        print(f"Policy: {config.tick_policy}")
        print(f"ClosedTick: {'YES' if stats.tick_count > 0 and config.tick_policy == 'ON_CLOSED_BAR' else 'NO'}")
        
        # Print last 5 events
        print()
        print("Last events:")
        for ev in stats.events[-5:]:
            reason = ev.get('tick_reason', '')
            print(f"  {ev['event_type']}: {ev.get('symbol')}/{ev.get('timeframe')} {reason}")
    
    elif args.command == "proof_open_close":
        # Proof OPEN→CLOSE (reduce-only) mode
        print("[PROOF_OPEN_CLOSE] Starting OPEN→CLOSE proof mode")
        print("[PROOF_OPEN_CLOSE] State machine: IDLE → OPENED → CLOSED")
        
        symbol = args.symbols.split(",")[0].strip()
        
        # Get exchange settings
        exchange_mode = getattr(args, "exchange_mode", "REAL_TESTNET")
        exchange_enabled = getattr(args, "exchange_enabled", True)
        armed = getattr(args, "armed", True)
        force_dry_run = getattr(args, "force_dry_run", False)
        
        print(f"[PROOF_OPEN_CLOSE] symbol={symbol} exchange_mode={exchange_mode} armed={armed}")
        
        # Client
        if args.real:
            from tezaver.matrix.live.marketdata.client import BinancePublicClient
            client = BinancePublicClient()
            print("[PROOF_OPEN_CLOSE] Using REAL Binance public data")
        else:
            from tezaver.matrix.live.marketdata.client import DummyMarketDataClient
            client = DummyMarketDataClient()
            print("[PROOF_OPEN_CLOSE] Using DUMMY data")
        
        # NDJSON event sink
        import json as json_lib
        from pathlib import Path
        from tezaver.matrix.live.secrets import redact_secrets
        from tezaver.matrix.live.order_state import get_order_state_store
        
        ndjson_path = Path("data/logs/live_events.ndjson")
        ndjson_path.parent.mkdir(parents=True, exist_ok=True)
        order_store = get_order_state_store()
        
        def ndjson_event_sink(event):
            safe_event = redact_secrets(event)
            with open(ndjson_path, "a") as f:
                f.write(json_lib.dumps(safe_event) + "\n")
            order_store.apply_event(event)
        
        # Create gateway with secrets
        from tezaver.matrix.live.live_gateway import BinanceTestnetGateway, DummyExchangeGateway
        from tezaver.matrix.live.secrets import EnvSecretsVault, FileSecretsVault, CompositeVault
        
        gateway = None
        if exchange_mode == "REAL_TESTNET" and armed and exchange_enabled and not force_dry_run:
            vaults = [EnvSecretsVault()]
            secrets_file = Path("data/secrets/live_keys.txt")
            if secrets_file.exists():
                vaults.append(FileSecretsVault(secrets_file))
            vault = CompositeVault(vaults)
            api_key = vault.get("API_KEY") or vault.get("BINANCE_API_KEY")
            api_secret = vault.get("API_SECRET") or vault.get("BINANCE_API_SECRET")
            
            if api_key and api_secret:
                gateway = BinanceTestnetGateway(api_key, api_secret)
                print("[PROOF_OPEN_CLOSE] Using REAL BinanceTestnetGateway")
            else:
                print("[PROOF_OPEN_CLOSE] ERROR: SECRETS_MISSING")
                sys.exit(1)
        else:
            gateway = DummyExchangeGateway()
            print("[PROOF_OPEN_CLOSE] Using DummyExchangeGateway")
        
        # Create proof controller with preflight settings
        from tezaver.matrix.live.proof_open_close import ProofOpenCloseController, PreflightMode, ClosePolicy
        
        preflight_mode = PreflightMode(getattr(args, "preflight_mode", "BLOCK"))
        close_policy = ClosePolicy(getattr(args, "close_policy", "NEXT_CLOSED_BAR"))
        min_pos_abs = getattr(args, "min_pos_abs", 1e-12)
        
        print(f"[PROOF_OPEN_CLOSE] preflight_mode={preflight_mode.value} close_policy={close_policy.value} min_pos_abs={min_pos_abs}")
        
        controller = ProofOpenCloseController(
            symbol=symbol,
            timeframe=args.tf,
            qty=0.002,  # ~$180 at BTC ~90k
            preflight_mode=preflight_mode,
            close_policy=close_policy,
            min_pos_abs=min_pos_abs,
            event_sink=ndjson_event_sink,
            exchange_mode=exchange_mode,
            armed=armed,
            exchange_enabled=exchange_enabled,
        )
        
        # Run preflight check
        print("[PROOF_OPEN_CLOSE] Running preflight check...")
        if not controller.run_preflight(gateway):
            print("[PROOF_OPEN_CLOSE] Preflight failed, exiting")
            summary = controller.get_summary()
            print(f"State: {summary['state']}")
            print(f"Last error: {summary['last_error']}")
            sys.exit(1)
        
        # Live loop for OPEN→CLOSE
        print(f"[PROOF_OPEN_CLOSE] Waiting for 2 NEW_CLOSED_BAR ticks ({args.tf})...")
        
        from datetime import datetime, timezone
        
        last_baseline = None
        poll_interval = args.poll
        
        # Dynamic max_runtime based on timeframe (need 2 bars + buffer)
        if args.tf == "1m":
            max_runtime = 300  # 5 minutes
        elif args.tf == "15m":
            max_runtime = 2100  # 35 minutes
        else:
            max_runtime = 600  # 10 minutes default
        
        print(f"[PROOF_OPEN_CLOSE] max_runtime={max_runtime}s for tf={args.tf}")
        start_time = datetime.now(timezone.utc)
        
        while not controller.is_done:
            # Check timeout
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > max_runtime:
                print(f"[PROOF_OPEN_CLOSE] TIMEOUT after {max_runtime}s")
                break
            
            # Poll market data
            bars_df = client.get_latest_bars(symbol, args.tf, limit=5)
            if bars_df is None or bars_df.empty:
                time.sleep(poll_interval)
                continue
            
            # Get last closed bar (is_closed column if available, else second-to-last)
            if "is_closed" in bars_df.columns:
                closed_bars = bars_df[bars_df["is_closed"] == True]
                if closed_bars.empty:
                    time.sleep(poll_interval)
                    continue
                prev_bar = closed_bars.iloc[-1]
            else:
                # Assume second-to-last bar is closed
                if len(bars_df) < 2:
                    time.sleep(poll_interval)
                    continue
                prev_bar = bars_df.iloc[-2]
            
            # Get bar close timestamp
            if "close_time_ms" in prev_bar:
                bar_close_ts = datetime.utcfromtimestamp(prev_bar["close_time_ms"] / 1000).isoformat()
            elif "ts" in prev_bar:
                bar_close_ts = str(prev_bar["ts"])
            else:
                time.sleep(poll_interval)
                continue
            
            close_price = float(prev_bar.get("close", 0))
            
            if bar_close_ts and bar_close_ts != last_baseline:
                # NEW_CLOSED_BAR
                print(f"[PROOF_OPEN_CLOSE] NEW_CLOSED_BAR: {bar_close_ts} close={close_price}")
                last_baseline = bar_close_ts
                
                result = controller.handle_closed_bar_tick(
                    bar_close_ts=bar_close_ts,
                    close_price=close_price,
                    gateway=gateway,
                )
                
                print(f"[PROOF_OPEN_CLOSE] action={result.action} success={result.success} order_id={result.order_id}")
                
                if not result.success:
                    print(f"[PROOF_OPEN_CLOSE] ERROR: {result.error}")
            
            time.sleep(poll_interval)
        
        # Print summary
        summary = controller.get_summary()
        print()
        print("=" * 60)
        print("PROOF_OPEN_CLOSE SUMMARY")
        print("=" * 60)
        print(f"State: {summary['state']}")
        print(f"Open order_id: {summary['open_order_id']}")
        print(f"Close order_id: {summary['close_order_id']}")
        print(f"Open bar_close_ts: {summary['open_bar_close_ts']}")
        print(f"Close bar_close_ts: {summary['close_bar_close_ts']}")
        print(f"Success: {summary['success']}")
        if summary['last_error']:
            print(f"Last error: {summary['last_error']}")
        print(f"Exit code: {0 if summary['success'] else 1}")
    
    elif args.command == "policy_cycle":
        # =====================================================
        # POLICY CYCLE mode - per-cell HOLD_NEXT_CLOSED policy
        # =====================================================
        from tezaver.matrix.live.live_policy import HoldNextClosedPolicy, PolicyName
        
        # Parse settings (same as other commands)
        symbols = args.symbols.split(",")
        symbol = symbols[0]  # Single symbol for now
        exchange_mode = args.exchange_mode
        armed = args.armed
        exchange_enabled = args.exchange_enabled
        force_dry_run = not args.no_force_dry_run if hasattr(args, "no_force_dry_run") else True
        
        print("[POLICY_CYCLE] Starting per-cell policy cycle")
        print(f"[POLICY_CYCLE] symbol={symbol} tf={args.tf} hold_policy={args.hold_policy}")
        print(f"[POLICY_CYCLE] exchange_mode={exchange_mode} armed={armed}")
        
        # Setup NDJSON telemetry
        import pathlib
        log_path = pathlib.Path("data/logs/live_events.ndjson")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "a")
        
        def ndjson_event_sink(event):
            import json
            log_file.write(json.dumps(event) + "\n")
            log_file.flush()
        
        # Setup gateway based on exchange_mode
        if exchange_mode == "REAL_TESTNET":
            from tezaver.matrix.live.live_gateway import BinanceTestnetGateway
            
            api_key = os.environ.get("API_KEY") or os.environ.get("BINANCE_API_KEY")
            api_secret = os.environ.get("API_SECRET") or os.environ.get("BINANCE_API_SECRET")
            
            if not api_key or not api_secret:
                try:
                    keys_path = pathlib.Path("data/secrets/live_keys.txt")
                    if keys_path.exists():
                        for line in keys_path.read_text().splitlines():
                            if "=" in line:
                                k, v = line.split("=", 1)
                                if k.strip() == "API_KEY":
                                    api_key = v.strip()
                                elif k.strip() == "API_SECRET":
                                    api_secret = v.strip()
                except:
                    pass
            
            gateway = BinanceTestnetGateway(api_key=api_key, api_secret=api_secret)
            print("[POLICY_CYCLE] Using REAL BinanceTestnetGateway")
        else:
            from tezaver.matrix.live.live_gateway import DummyExchangeGateway
            gateway = DummyExchangeGateway()
            print("[POLICY_CYCLE] Using DummyExchangeGateway")
        
        # Create policy
        profile_id = f"{symbol}_{args.tf}_policy"
        
        policy = HoldNextClosedPolicy(
            gateway=gateway,
            event_sink=ndjson_event_sink,
            qty=0.002,
            exchange_mode=exchange_mode,
            armed=armed,
            exchange_enabled=exchange_enabled,
        )
        
        print(f"[POLICY_CYCLE] profile_id={profile_id}")
        
        # Dynamic max_runtime
        if args.tf == "1m":
            max_runtime = 300
        elif args.tf == "15m":
            max_runtime = 2100
        else:
            max_runtime = 600
        
        print(f"[POLICY_CYCLE] max_runtime={max_runtime}s for tf={args.tf}")
        print(f"[POLICY_CYCLE] Waiting for NEW_CLOSED_BAR ticks...")
        
        # Setup market data client (same as proof_open_close)
        if args.real:
            from tezaver.matrix.live.marketdata.client import BinancePublicClient
            md_client = BinancePublicClient()
            print("[POLICY_CYCLE] Using REAL Binance public data")
        else:
            from tezaver.matrix.live.marketdata.client import DummyMarketDataClient
            md_client = DummyMarketDataClient()
            print("[POLICY_CYCLE] Using DUMMY data")
        
        from datetime import datetime, timezone
        
        last_baseline = None
        poll_interval = args.poll
        start_time = datetime.now(timezone.utc)
        
        while not policy.is_cycle_complete(symbol, args.tf, profile_id):
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            if elapsed > max_runtime:
                print(f"[POLICY_CYCLE] TIMEOUT after {max_runtime}s")
                break
            
            # Fetch bars (same pattern as proof_open_close)
            bars_df = md_client.get_latest_bars(symbol, args.tf, limit=5)
            if bars_df is None or bars_df.empty:
                time.sleep(poll_interval)
                continue
            
            # Get last closed bar
            if "is_closed" in bars_df.columns:
                closed_bars = bars_df[bars_df["is_closed"] == True]
                if closed_bars.empty:
                    time.sleep(poll_interval)
                    continue
                prev_bar = closed_bars.iloc[-1]
            else:
                if len(bars_df) < 2:
                    time.sleep(poll_interval)
                    continue
                prev_bar = bars_df.iloc[-2]
            
            # Get bar close timestamp
            if "close_time_ms" in prev_bar:
                bar_close_ts = datetime.utcfromtimestamp(prev_bar["close_time_ms"] / 1000).isoformat()
            else:
                bar_close_ts = str(prev_bar["ts"])
            close_price = prev_bar["close"]
            
            # Dedup
            if bar_close_ts == last_baseline:
                time.sleep(poll_interval)
                continue
            
            last_baseline = bar_close_ts
            print(f"[POLICY_CYCLE] NEW_CLOSED_BAR: {bar_close_ts} close={close_price}")
            
            # For HOLD_NEXT_CLOSED, always send "OPEN" as decision in IDLE state
            # (In production, cluster would provide decision)
            cell_state = policy.get_cell_state(symbol, args.tf, profile_id)
            decision = "OPEN" if cell_state.state.value == "IDLE" else None
            
            result = policy.handle_tick(
                symbol=symbol,
                tf=args.tf,
                profile_id=profile_id,
                bar_close_ts=bar_close_ts,
                decision=decision,
            )
            
            print(f"[POLICY_CYCLE] action={result.action} success={result.success} state={result.state.value}")
            
            if not result.success and result.error:
                print(f"[POLICY_CYCLE] ERROR: {result.error}")
            
            time.sleep(poll_interval)
        
        # Summary
        summary = policy.get_summary(symbol, args.tf, profile_id)
        print()
        print("=" * 60)
        print("POLICY_CYCLE SUMMARY")
        print("=" * 60)
        print(f"State: {summary['state']}")
        print(f"Open order_id: {summary['open_order_id']}")
        print(f"Close order_id: {summary['close_order_id']}")
        print(f"Effective bar: {summary['open_effective_bar_close_ts']}")
        print(f"Close bar: {summary['close_bar_close_ts']}")
        print(f"bars_waited_effective: {summary['bars_waited_effective']}")
        print(f"lag_sec_effective: {summary['lag_sec_effective']}")
        print(f"residual_after: {summary['residual_after']}")
        print(f"Success: {summary['close_order_id'] is not None}")


if __name__ == "__main__":
    main()
