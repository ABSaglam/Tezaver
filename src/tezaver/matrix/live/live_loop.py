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
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from tezaver.matrix.live.marketdata.client import IMarketDataClient, DummyMarketDataClient
from tezaver.matrix.live.marketdata.cache import BarCache
from tezaver.matrix.live.marketdata.snapshot_builder import build_snapshot_from_bars
from tezaver.matrix.live.marketdata.snapshot_builder import build_snapshot_from_bars
from tezaver.matrix.live.preflight import run_preflight, PreflightContext, BLOCK as PREFLIGHT_BLOCK
from tezaver.matrix.live.incident_bundle import export_incident_bundle, BundleContext, emit_export_telemetry


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
    # Order Lifecycle Config
    poll_order_sec: float = 2.0
    order_timeout_sec: float = 30.0
    cancel_on_timeout: bool = False
    inject_fault: str = "NONE"


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


def emit_incident_bundle_telemetry(
    symbol: str,
    timeframe: str,
    cycle_idx: int,
    alert_level: str,
    out_path: str,
    files_count: int,
) -> None:
    """Emit INCIDENT_BUNDLE_CREATED telemetry event to NDJSON."""
    import json
    from datetime import datetime, timezone
    from pathlib import Path
    from tezaver.matrix.live.cycle_events import redact_event_secrets
    
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event_type": "INCIDENT_BUNDLE_CREATED",
        "symbol": symbol,
        "timeframe": timeframe,
        "cycle_idx": cycle_idx,
        "alert_level": alert_level,
        "out_path": out_path,
        "files_count": files_count,
    }
    
    # Redact before writing (defensive, though no secrets expected)
    safe_event = redact_event_secrets(event)
    
    ndjson_path = Path("data/logs/live_events.ndjson")
    ndjson_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(ndjson_path, "a") as f:
        f.write(json.dumps(safe_event, default=str) + "\n")


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
    parser.add_argument("command", choices=["run", "proof_router", "proof_router_cluster", "proof_open_close", "policy_cycle", "report_cycles", "reconcile"], help="Command to run")
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
    
    # =========================================================================
    # MAINNET SAFETY FLAGS (F1+F2)
    # =========================================================================
    parser.add_argument("--mainnet-arm", action="store_true", default=False,
                       help="REQUIRED for REAL_MAINNET: explicitly arm mainnet trading")
    parser.add_argument("--mainnet-ack", type=str, default=None,
                       help="REQUIRED for REAL_MAINNET: acknowledgment string (must be 'I_UNDERSTAND_REAL_MAINNET')")
    parser.add_argument("--mainnet-max-notional", type=float, default=None,
                       help="REQUIRED for REAL_MAINNET: max total notional in USD (e.g., 1000)")
    parser.add_argument("--mainnet-allowlist", type=str, default=None,
                       help="REQUIRED for REAL_MAINNET: comma-separated allowed symbols (e.g., 'BTCUSDT,ETHUSDT')")
    
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
    
    # Strategy arguments
    parser.add_argument("--strategy-enabled", action="store_true", default=False,
                       help="Enable strategy signal adapter")
    parser.add_argument("--open-rule-mode", type=str, default="ALWAYS_OFF",
                       choices=["ALWAYS_OFF", "AUTO_OPEN_FLAT", "CARD_STRICT_WINDOW", "CARD_SOURCE_WINDOW"],
                       help="Strategy open rule mode")
    parser.add_argument("--cooldown-bars", type=int, default=1,
                       help="Cooldown bars between actions")
    parser.add_argument("--contract-enforce", type=str, default="WARN",
                       choices=["WARN", "BLOCK"],
                       help="Contract enforcement mode")
    parser.add_argument("--profile-id", type=str, default="SILVER_15m",
                       help="Strategy profile ID")
    parser.add_argument("--close-rule-mode", type=str, default="ALWAYS_OFF",
                       choices=["ALWAYS_OFF", "CLOSE_ON_NEXT_SIGNAL"],
                       help="Strategy close rule mode: ALWAYS_OFF or CLOSE_ON_NEXT_SIGNAL")
    parser.add_argument("--min-hold-bars", type=int, default=1,
                       help="Minimum bars to hold before CLOSE on NEXT_SIGNAL policy")
    parser.add_argument("--cycles", type=int, default=1,
                       help="Number of OPEN→CLOSE cycles to run (default 1)")
    parser.add_argument("--sleep-between-cycles", type=float, default=0,
                       help="Seconds to sleep between cycles (default 0)")
    parser.add_argument("--cycle-timeout-bars", type=int, default=8,
                       help="Max bars per cycle before timeout (default 8)")
    parser.add_argument("--open-timeout-bars", type=int, default=4,
                       help="Max bars waiting for OPEN signal (default 4)")
    parser.add_argument("--close-timeout-bars", type=int, default=4,
                       help="Max bars waiting for CLOSE signal after EFFECTIVE_SET (default 4)")
    parser.add_argument("--stall-timeout-sec", type=int, default=0,
                       help="Seconds with no NEW_CLOSED_BAR before STALL timeout (0=auto: 2*tf_sec + 60)")
    parser.add_argument("--audit", action="store_true",
                       help="Enable Trade Audit V2 at end of each cycle (fetch order details, fees)")
    parser.add_argument("--last", type=int, default=10,
                       help="Number of last cycles to show in report_cycles command")
    parser.add_argument("--only", type=str, default=None,
                       choices=["WARN", "BLOCK"],
                       help="Filter cycles by alert level (WARN includes BLOCK)")
    parser.add_argument("--equity-start", type=float, default=100.0,
                       help="Starting equity for equity curve calculation")
    parser.add_argument("--print-metrics", action="store_true",
                       help="Print risk metrics in report_cycles")
    parser.add_argument("--cycle-idx", type=int, default=None,
                       help="Specific cycle index to show timeline for")
    parser.add_argument("--show-timeline", action="store_true",
                       help="Show event timeline for --cycle-idx")
    parser.add_argument("--export-json", type=str, default=None,
                       help="Export cycles to JSON file path")
    parser.add_argument("--only-types", type=str, default=None,
                       help="Filter timeline by event types (comma-separated)")
    parser.add_argument("--raw-json", action="store_true",
                       help="Print full event JSON (redacted) for timeline")
    parser.add_argument("--grep", type=str, default=None,
                       help="Filter timeline events by substring match")
    parser.add_argument("--export-bundle", action="store_true",
                       help="Export incident bundle for --cycle-idx")
    parser.add_argument("--out-dir", type=str, default="data/incidents",
                       help="Output directory for incident bundles")
    parser.add_argument("--only-relevant", action="store_true",
                       help="Filter to relevant event types only")
    parser.add_argument("--auto-incident-on", type=str, default=None,
                        choices=["BLOCK", "WARN", "OFF"],
                        help="(DEPRECATED: use --auto-export-on-block) Legacy auto-incident trigger level")
    parser.add_argument("--auto-incident-out-dir", type=str, default="data/incidents",
                       help="Output directory for auto-incident bundles")
    parser.add_argument("--auto-incident-only-relevant", action="store_true", default=True,
                       help="Filter to relevant event types only in auto bundles")
    parser.add_argument("--auto-incident-max", type=int, default=1,
                       help="Max number of incident bundles to auto-export (last N matching)")
    
    # Order Lifecycle Arguments (New in v1)
    parser.add_argument(
        "--inject-order-fault",
        type=str,
        default="NONE",
        choices=["NONE", "PARTIAL", "REJECT", "TIMEOUT", "TIMEOUT_OPEN", "TIMEOUT_CLOSE"],
        help="Simulate order failure (TIMEOUT/REJECT/PARTIAL)"
    )
    parser.add_argument("--order-timeout-sec", type=float, default=30.0,
        help="Max seconds to wait for order fill before timeout")
    parser.add_argument("--poll-order-sec", type=float, default=2.0,
                       help="Interval for polling order status")
    parser.add_argument("--cancel-on-timeout", action="store_true",
                       help="Cancel order if timeout reached (default: leave open/unknown)")
    parser.add_argument("--inject-order-fault-nth", type=int, default=0,
                       help="Only inject fault on Nth order (0=all orders, 1=first, 2=second/CLOSE)")
    parser.add_argument("--inject-order-fault-action", type=str, default="ANY",
                       choices=["ANY", "OPEN", "CLOSE"],
                       help="Only inject fault on specific action (ANY/OPEN/CLOSE)")
    # Risk Limiter CLI args
    parser.add_argument("--max-total-notional-usdt", type=float, default=500.0,
                       help="Max total notional USDT across all cells")
    parser.add_argument("--max-cell-notional-usdt", type=float, default=300.0,
                       help="Max notional USDT per cell")
    parser.add_argument("--max-open-positions", type=int, default=3,
                       help="Max number of open positions")
    parser.add_argument("--risk-enforce", type=str, default="BLOCK",
                       choices=["WARN", "BLOCK"],
                       help="Risk limit enforcement mode")
    # Card Gate CLI args
    parser.add_argument("--card-gate-enabled", action="store_true", default=True,
                       help="Enable card governance gate")
    parser.add_argument("--no-card-gate-enabled", action="store_false", dest="card_gate_enabled",
                       help="Disable card governance gate")
    parser.add_argument("--card-max-age-hours", type=float, default=72.0,
                       help="Max card age in hours before stale")
    parser.add_argument("--card-enforce-mode", type=str, default="BLOCK",
                       choices=["WARN", "BLOCK"],
                       help="Card gate enforcement mode")
    parser.add_argument("--card-force-stale", action="store_true",
                       help="Force card stale for testing")
    parser.add_argument("--card-force-drift", action="store_true",
                       help="Force card drift for testing")
    
    # Preflight Arguments (v1)
    parser.add_argument("--preflight", action="store_true", help="Run preflight checks before starting")
    parser.add_argument("--preflight-enforce", type=str, default="WARN", choices=["WARN", "BLOCK"], help="Enforcement mode for preflight (default: WARN)")

    # Incident Bundle Arguments (v1)
    parser.add_argument("--auto-export-on-block", action="store_true", help="Auto-export incident bundle on BLOCK")
    parser.add_argument("--incident-last-n-events", type=int, default=500, help="Events to include in bundle")
    parser.add_argument("--incident-last-n-log-lines", type=int, default=300, help="Log lines to include in bundle")
    parser.add_argument("--incident-dir", type=str, default="data/incidents", help="Incident output directory")

    args = parser.parse_args()
    
    # Legacy flag mapping: --auto-incident-on -> --auto-export-on-block
    if args.auto_incident_on is not None and args.auto_incident_on != "OFF":
        print("[DEPRECATED] --auto-incident-on is deprecated. Use --auto-export-on-block instead.")
        if not args.auto_export_on_block:  # Don't override if new flag explicitly set
            args.auto_export_on_block = True
    
    # =========================================================================
    # F1+F2: MAINNET GUARD CHECK
    # =========================================================================
    def check_mainnet_guard(args, ndjson_sink=None):
        """Check REAL_MAINNET safety requirements. Returns (pass, reasons)."""
        if args.exchange_mode != "REAL_MAINNET":
            return True, []
        
        reasons = []
        
        # F1: Require explicit arm + ack
        if not args.mainnet_arm:
            reasons.append("MISSING_MAINNET_ARM")
        if args.mainnet_ack != "I_UNDERSTAND_REAL_MAINNET":
            reasons.append("MISSING_OR_WRONG_MAINNET_ACK")
        
        # F2: Require safety prerequisites
        if not args.preflight:
            reasons.append("PREFLIGHT_NOT_ENABLED")
        if not args.auto_export_on_block:
            reasons.append("AUTO_EXPORT_NOT_ENABLED")
        if args.mainnet_max_notional is None:
            reasons.append("MISSING_MAINNET_MAX_NOTIONAL")
        if not args.mainnet_allowlist:
            reasons.append("MISSING_MAINNET_ALLOWLIST")
        
        decision = "PASS" if not reasons else "BLOCK"
        
        # Emit telemetry
        if ndjson_sink:
            from datetime import datetime as _dt, timezone as _tz
            ndjson_sink({
                "event_type": "MAINNET_GUARD_EVAL",
                "ts": _dt.now(_tz.utc).isoformat(),
                "decision": decision,
                "reasons": reasons,
                "mainnet_arm": args.mainnet_arm,
                "mainnet_ack_provided": args.mainnet_ack is not None,
                "mainnet_max_notional": args.mainnet_max_notional,
                "mainnet_allowlist": args.mainnet_allowlist,
                "preflight": args.preflight,
                "auto_export": args.auto_export_on_block,
            })
        
        return decision == "PASS", reasons
    
    # =========================================================================
    # Early NDJSON sink for mainnet guard telemetry (before command-specific sinks)
    # =========================================================================
    def _early_ndjson_sink(event):
        """Write event to NDJSON file (early, before full sinks defined)."""
        from pathlib import Path
        import json
        ndjson_path = Path("data/logs/live_events.ndjson")
        ndjson_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(ndjson_path, "a") as f:
                f.write(json.dumps(event) + "\n")
        except:
            pass
    
    # =========================================================================
    # Allowlist enforcement helper
    # =========================================================================
    def enforce_allowlist(requested_symbols: list, allowlist_str: str) -> tuple:
        """
        Check if requested symbols are in the allowlist.
        Returns (allowed, blocked_symbols).
        """
        if not allowlist_str:
            return False, requested_symbols
        
        allowed_set = {s.strip().upper() for s in allowlist_str.split(",") if s.strip()}
        requested_upper = [s.upper() for s in requested_symbols]
        blocked = [s for s in requested_upper if s not in allowed_set]
        
        return len(blocked) == 0, blocked
    
    # Run mainnet guard (with NDJSON telemetry)
    if args.exchange_mode == "REAL_MAINNET":
        mainnet_ok, mainnet_reasons = check_mainnet_guard(args, _early_ndjson_sink)
        
        if not mainnet_ok:
            print(f"⛔ MAINNET_GUARD_BLOCK: {mainnet_reasons}")
            print("Required for REAL_MAINNET:")
            print("  --mainnet-arm")
            print("  --mainnet-ack 'I_UNDERSTAND_REAL_MAINNET'")
            print("  --preflight --auto-export-on-block")
            print("  --mainnet-max-notional <value>")
            print("  --mainnet-allowlist 'SYM1,SYM2'")
            sys.exit(2)
        
        # Allowlist enforcement (after guard passes)
        requested_symbols = [s.strip() for s in args.symbols.split(",")]
        allowlist_ok, blocked_syms = enforce_allowlist(requested_symbols, args.mainnet_allowlist)
        
        if not allowlist_ok:
            reason = f"ALLOWLIST_VIOLATION:{blocked_syms}"
            from datetime import datetime as _dt2, timezone as _tz2
            _early_ndjson_sink({
                "event_type": "MAINNET_GUARD_EVAL",
                "ts": _dt2.now(_tz2.utc).isoformat(),
                "decision": "BLOCK",
                "reasons": [reason],
                "mainnet_allowlist": args.mainnet_allowlist,
                "requested_symbols": requested_symbols,
            })
            print(f"⛔ MAINNET_GUARD_BLOCK: {[reason]}")
            print(f"Requested symbols {requested_symbols} not in allowlist: {args.mainnet_allowlist}")
            sys.exit(2)
        
        # Emit MAINNET_ARMED to NDJSON
        from datetime import datetime as dt_now, timezone as tz
        _early_ndjson_sink({
            "event_type": "MAINNET_ARMED",
            "ts": dt_now.now(tz.utc).isoformat(),
            "mainnet_max_notional": args.mainnet_max_notional,
            "mainnet_allowlist": args.mainnet_allowlist,
            "symbols": requested_symbols,
            "mode": args.exchange_mode,
            "scope": "GLOBAL",
        })
        print(f"[MAINNET_ARMED] ts={dt_now.now(tz.utc).isoformat()} max_notional={args.mainnet_max_notional} allowlist={args.mainnet_allowlist}")
        print("[MAINNET_ARMED] All safety checks passed. Live trading enabled.")
    
    # Single-export guard
    _block_exported = [False]  # Use list for mutable closure
    
    # Helper: Handle BLOCK exit with auto-export
    def handle_block_exit(reason: str, exit_code: int = 2, config_map: dict = None):
        # Guard: export at most once per process
        if args.auto_export_on_block and not _block_exported[0]:
            _block_exported[0] = True
            from pathlib import Path
            ctx = BundleContext(
                reason=reason,
                ndjson_path=Path("data/logs/live_events.ndjson"),
                config=config_map,
                output_dir=Path(args.incident_dir),
                last_n_events=args.incident_last_n_events,
                last_n_log_lines=args.incident_last_n_log_lines,
                cmdline=" ".join(sys.argv)
            )
            bundle_path = export_incident_bundle(ctx)
            emit_export_telemetry(ctx.ndjson_path, bundle_path, reason, 4)
            print(f"incident_bundle={bundle_path}")
            
        print(f"⛔ BLOCK EXIT: {reason}")
        if exit_code is not None:
            sys.exit(exit_code)

    # Exec Preflight if requested (Global)
    if args.preflight:
        # Construct config for preflight context
        pf_config = LiveLoopConfig(
            poll_interval_sec=args.poll,
            tick_policy=args.policy,
            max_runtime_sec=args.runtime,
            dry_run=not args.real
        )
        symbols = [s.strip() for s in args.symbols.split(",")]
        
        ctx = PreflightContext(
            args=args,
            config=pf_config,
            symbols=symbols,
            timeframe=args.tf
        )
        
        result = run_preflight(ctx, enforce_mode=args.preflight_enforce)
        
        if result.decision == PREFLIGHT_BLOCK:
            handle_block_exit(f"PREFLIGHT_BLOCK: {result.summary}", config_map=asdict(pf_config))
    
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
                                # Lifecycle Config
                                poll_interval_sec=args.poll_order_sec,
                                order_timeout_sec=args.order_timeout_sec,
                                cancel_on_timeout=args.cancel_on_timeout,
                                inject_fault=args.inject_order_fault,
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
        # Prepare Gateway for Policy (if needed)
        policy_gateway = None
        
        # Assume hold_policy is defined from args or elsewhere, e.g., hold_policy = getattr(args, "hold_policy", "NONE")
        hold_policy = getattr(args, "hold_policy", "NONE") # Added for context, assuming it comes from args
        
        if hold_policy == "HOLD_NEXT_CLOSED":
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
                    print("[PROOF_ROUTER_CLUSTER] Using REAL BinanceTestnetGateway for Policy")
                else:
                    print("[PROOF_ROUTER_CLUSTER] WARN: Secrets missing, falling back to DUMMY for Policy")
                    policy_gateway = DummyExchangeGateway()
            
            elif exchange_mode == "DUMMY_ORDER" or exchange_mode == "DRY_RUN":
                 policy_gateway = DummyExchangeGateway()
                 print("[PROOF_ROUTER_CLUSTER] Using DummyExchangeGateway for Policy")
        
        # Router Config
        router_config = LiveRouterConfig(
            enabled=True,
            exchange_mode=exchange_mode,
            armed=armed,
            exchange_enabled=exchange_enabled,
            hold_policy=hold_policy,
            force_dry_run=force_dry_run,
            only_symbols=symbols,
            only_timeframes=[args.tf],
            strategy_enabled=True,  # Enable strategy to drive Policy OPEN triggers
            # Lifecycle Config
            poll_order_sec=args.poll_order_sec,
            order_timeout_sec=args.order_timeout_sec,
            cancel_on_timeout=args.cancel_on_timeout,
            inject_fault=args.inject_order_fault,
            # Risk Limiter Config (override with mainnet cap if armed)
            max_total_notional_usdt=(args.mainnet_max_notional if args.exchange_mode == "REAL_MAINNET" and args.mainnet_max_notional else getattr(args, "max_total_notional_usdt", 500.0)),
            max_cell_notional_usdt=getattr(args, "max_cell_notional_usdt", 300.0),
            max_open_positions=getattr(args, "max_open_positions", 3),
            risk_enforce=getattr(args, "risk_enforce", "BLOCK"),
        )
        
        router = MatrixLiveRouter(
            cluster=stub_cluster, 
            config=router_config, 
            event_sink=ndjson_event_sink,
            gateway=policy_gateway  # Inject the gateway
        )
        
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
        policy_result_summary = {}
        
        # Policy setup moved above
        if use_policy_cycle:
            from tezaver.matrix.live.live_policy import HoldNextClosedPolicy, PolicyState            
            symbol = symbols[0]
            profile_id = f"{symbol}_{args.tf}_policy"
            
            # Get dust policy params
            dust_policy = getattr(args, "dust_policy", "IGNORE")
            dust_threshold = getattr(args, "dust_threshold", 0.002)
            close_qty_mult = getattr(args, "close_qty_mult", 1.0)
            close_policy_arg = getattr(args, "close_policy", "NEXT_CLOSED_BAR")
            min_hold_bars_arg = getattr(args, "min_hold_bars", 1)
            
            # Create GlobalRiskLimiter for pre-trade checks
            from tezaver.matrix.live.risk_limiter import GlobalRiskLimiter, RiskLimits
            policy_risk_limiter = GlobalRiskLimiter(
                limits=RiskLimits(
                    max_total_notional_usdt=(args.mainnet_max_notional if args.exchange_mode == "REAL_MAINNET" and args.mainnet_max_notional else getattr(args, "max_total_notional_usdt", 500.0)),
                    max_cell_notional_usdt=getattr(args, "max_cell_notional_usdt", 300.0),
                    max_open_positions=getattr(args, "max_open_positions", 3),
                    enforce=getattr(args, "risk_enforce", "BLOCK"),
                ),
                event_sink=ndjson_event_sink,
            )
            
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
                close_policy=close_policy_arg,
                min_hold_bars=min_hold_bars_arg,
                # Lifecycle Config
                poll_order_sec=getattr(args, "poll_order_sec", 2.0),
                order_timeout_sec=getattr(args, "order_timeout_sec", 60),
                cancel_on_timeout=getattr(args, "cancel_on_timeout", False),
                inject_fault=getattr(args, "inject_order_fault", None),
                inject_fault_nth=getattr(args, "inject_order_fault_nth", 0),
                inject_fault_action=getattr(args, "inject_order_fault_action", "ANY"),
                risk_limiter=policy_risk_limiter,  # Pass risk limiter for pre-trade checks
                auto_export_on_block=args.auto_export_on_block,
                mainnet_allowlist=getattr(args, "mainnet_allowlist", None),
            )
            
            print(f"[PROOF_ROUTER_CLUSTER] Policy profile_id={profile_id}")
            print(f"[PROOF_ROUTER_CLUSTER] close_policy={close_policy_arg} min_hold_bars={min_hold_bars_arg} dust_policy={dust_policy}")
            
            # Compute dynamic max_runtime based on bar timeouts (never preempt bar logic)
            tf_sec = {
                "1m": 60, "3m": 180, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400
            }.get(args.tf, 900)
            
            # Bar-based deadline: cycles * cycle_bars * tf_sec + buffer
            bar_based_deadline = args.cycles * args.cycle_timeout_bars * tf_sec + (2 * tf_sec + 60)
            
            # Use max of legacy and bar-based to ensure bar logic has priority
            effective_max_runtime = max(max_runtime, bar_based_deadline)
            
            # Stall timeout (no NEW_CLOSED_BAR for too long)
            stall_timeout = args.stall_timeout_sec if args.stall_timeout_sec > 0 else (2 * tf_sec + 60)
            
            print(f"[PROOF_ROUTER_CLUSTER] max_runtime={effective_max_runtime}s (bar_deadline={bar_based_deadline}s) for tf={args.tf}")
            print(f"[PROOF_ROUTER_CLUSTER] stall_timeout={stall_timeout}s, cycle_timeout_bars={args.cycle_timeout_bars}")
            print("[PROOF_ROUTER_CLUSTER] Waiting for NEW_CLOSED_BAR ticks (policy mode)...")
        
        # Create StrategySignalAdapter if enabled
        strategy_adapter = None
        strategy_enabled = getattr(args, "strategy_enabled", False)
        
        if strategy_enabled:
            from tezaver.matrix.live.strategy_signal import StrategySignalAdapter, PositionStateStore
            
            position_store = PositionStateStore()
            strategy_adapter = StrategySignalAdapter(
                position_store=position_store,
                event_sink=ndjson_event_sink,
                open_rule_mode=getattr(args, "open_rule_mode", "ALWAYS_OFF"),
                min_bars_between_actions=getattr(args, "cooldown_bars", 1),
                contract_enforce=getattr(args, "contract_enforce", "WARN"),
                profile_id=getattr(args, "profile_id", "SILVER_15m"),
                close_rule_mode=getattr(args, "close_rule_mode", "ALWAYS_OFF"),
            )
            print(f"[PROOF_ROUTER_CLUSTER] StrategySignalAdapter open_rule_mode={getattr(args, 'open_rule_mode', 'ALWAYS_OFF')}")
        
        # Create CardGate for card governance
        card_gate = None
        from tezaver.matrix.live.card_gate import CardGate, CardGateConfig
        card_gate_config = CardGateConfig(
            enabled=getattr(args, "card_gate_enabled", True),
            max_age_hours=getattr(args, "card_max_age_hours", 72.0),
            enforce_mode=getattr(args, "card_enforce_mode", "BLOCK"),
            force_stale=getattr(args, "card_force_stale", False),
            force_drift=getattr(args, "card_force_drift", False),
        )
        card_gate = CardGate(config=card_gate_config, event_sink=ndjson_event_sink)
        print(f"[PROOF_ROUTER_CLUSTER] CardGate enabled={card_gate_config.enabled} enforce={card_gate_config.enforce_mode} force_stale={card_gate_config.force_stale} force_drift={card_gate_config.force_drift}")
        
        # Current cycle idx for propagation to policy (set by main loop)
        current_cycle_idx = 1
        
        # Event callback to route closed bar ticks
        def on_event(event):
            nonlocal policy, policy_result_summary, current_cycle_idx
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
                    
                    # Strategy signal adapter - emit STRATEGY_SIGNAL on every tick
                    strategy_signal_value = None
                    if strategy_adapter:
                        strategy_signal = strategy_adapter.compute_signal(
                            symbol=symbol,
                            tf=tf,
                            profile_id=profile_id,
                            bar_close_ts=bar_close_ts,
                            snapshot=snapshot,
                        )
                        strategy_signal_value = strategy_signal.value  # Convert enum to string
                    
                    # CardGate evaluation
                    card_gate_result = None
                    card_gate_allow = True
                    if card_gate:
                        open_rule_mode = getattr(args, "open_rule_mode", "ALWAYS_OFF")
                        cell_id = f"{symbol}|{tf}|{profile_id}"
                        card_gate_result = card_gate.evaluate(
                            symbol=symbol,
                            timeframe=tf,
                            profile_id=profile_id,
                            cell_id=cell_id,
                            open_rule_mode=open_rule_mode,
                            cycle_idx=current_cycle_idx,
                        )
                        card_gate_allow = card_gate_result.allow
                        if not card_gate_allow:
                            print(f"[GUARDRAIL] CARD_GATE_{card_gate_result.gate} {cell_id}: {card_gate_result.violations}")
                            # Export incident bundle on CardGate BLOCK (once per process)
                            handle_block_exit(f"CardGate_{card_gate_result.gate}: {card_gate_result.violations}", exit_code=None)
                    
                    # Get cell state to determine decision
                    cell_state = policy.get_cell_state(symbol, tf, profile_id)
                    # V5: OPEN decision only if strategy says OPEN_LONG AND card_gate allows
                    decision = "OPEN" if (cell_state.state.value == "IDLE" and strategy_signal_value == "OPEN_LONG" and card_gate_allow) else None
                    
                    result = policy.handle_tick(
                        symbol=symbol,
                        tf=tf,
                        profile_id=profile_id,
                        bar_close_ts=bar_close_ts,
                        decision=decision,
                        strategy_signal=strategy_signal_value,
                        cycle_idx=current_cycle_idx,
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
            
            # Multi-cycle support
            total_cycles = args.cycles
            cycle_results = []
            
            print(f"[PROOF_ROUTER_CLUSTER] Running {total_cycles} cycle(s)")
            
            for cycle_idx in range(total_cycles):
                # CYCLE_START
                ndjson_event_sink({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event_type": "CYCLE_START",
                    "cycle_idx": cycle_idx + 1,
                    "total_cycles": total_cycles,
                    "symbol": symbol,
                    "timeframe": args.tf,
                })
                print(f"\n{'='*60}")
                print(f"CYCLE {cycle_idx + 1}/{total_cycles} STARTED")
                print(f"{'='*60}")
                
                # Update current_cycle_idx for propagation to policy events
                current_cycle_idx = cycle_idx + 1
                
                # Reset policy state for new cycle
                if cycle_idx > 0:
                    policy.reset_cell(symbol, args.tf, profile_id)
                    if args.sleep_between_cycles > 0:
                        print(f"[PROOF_ROUTER_CLUSTER] Sleeping {args.sleep_between_cycles}s between cycles...")
                        time.sleep(args.sleep_between_cycles)
                
                # Manual loop for policy cycle
                last_baseline = None
                start_time = datetime.now(timezone.utc)
                poll_count = 0
                tick_count = 0
                skip_count = 0
                
                # Bar-based timeout tracking
                cycle_bars = 0
                phase_bars = 0
                current_phase = "WAIT_OPEN"
                last_phase = None
                cycle_timed_out = False
                timeout_reason = None
                last_new_bar_ts = datetime.now(timezone.utc)  # Track stall
                
                while not policy.is_cycle_complete(symbol, args.tf, profile_id):
                    now = datetime.now(timezone.utc)
                    elapsed = (now - start_time).total_seconds()
                    
                    # Stall timeout: no NEW_CLOSED_BAR for too long
                    stall_sec = (now - last_new_bar_ts).total_seconds()
                    if stall_sec > stall_timeout:
                        print(f"[PROOF_ROUTER_CLUSTER] STALL_TIMEOUT: no NEW_CLOSED_BAR for {stall_sec:.0f}s")
                        cycle_timed_out = True
                        timeout_reason = f"STALL_NO_NEW_BAR({stall_sec:.0f}s)"
                        break
                    
                    # Overall wall-clock deadline (as safety net, should not trigger if bars flowing)
                    if elapsed > effective_max_runtime:
                        print(f"[PROOF_ROUTER_CLUSTER] OVERALL_DEADLINE after {effective_max_runtime}s")
                        cycle_timed_out = True
                        timeout_reason = f"OVERALL_DEADLINE({effective_max_runtime}s)"
                        break
                    
                    # Bar-based timeouts
                    if cycle_bars >= args.cycle_timeout_bars:
                        timeout_reason = f"CYCLE_BARS_EXCEEDED({cycle_bars}/{args.cycle_timeout_bars})"
                        print(f"[PROOF_ROUTER_CLUSTER] BAR TIMEOUT: {timeout_reason}")
                        cycle_timed_out = True
                        break
                    
                    if current_phase == "WAIT_OPEN" and phase_bars >= args.open_timeout_bars:
                        timeout_reason = f"OPEN_TIMEOUT_BARS({phase_bars}/{args.open_timeout_bars})"
                        print(f"[PROOF_ROUTER_CLUSTER] BAR TIMEOUT: {timeout_reason}")
                        cycle_timed_out = True
                        break
                    
                    if current_phase == "WAIT_CLOSE" and phase_bars >= args.close_timeout_bars:
                        timeout_reason = f"CLOSE_TIMEOUT_BARS({phase_bars}/{args.close_timeout_bars})"
                        print(f"[PROOF_ROUTER_CLUSTER] BAR TIMEOUT: {timeout_reason}")
                        cycle_timed_out = True
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
                    cycle_bars += 1
                    phase_bars += 1
                    last_new_bar_ts = datetime.now(timezone.utc)  # Reset stall timer
                    
                    print(f"[PROOF_ROUTER_CLUSTER] NEW_CLOSED_BAR: {bar_close_ts} close={close_price} (cycle_bars={cycle_bars} phase={current_phase} phase_bars={phase_bars})")
                    
                    # Emit CLOSED_PROOF event (triggers on_event)
                    on_event({
                        "event_type": "CLOSED_PROOF",
                        "symbol": symbol,
                        "timeframe": args.tf,
                        "bar_close_ts": bar_close_ts,
                        "close": close_price,
                    })
                    
                    # Update phase based on policy state
                    cell_state = policy.get_cell_state(symbol, args.tf, profile_id)
                    new_phase = current_phase
                    if cell_state.state.value in ["OPEN_SUBMITTED", "EFFECTIVE_SET"]:
                        new_phase = "WAIT_CLOSE"
                    elif cell_state.state.value == "IDLE" and cell_state.open_order_id is not None:
                        new_phase = "DONE"
                    
                    # Reset phase_bars on phase change
                    if new_phase != current_phase:
                        print(f"[PROOF_ROUTER_CLUSTER] PHASE_CHANGE: {current_phase} -> {new_phase}")
                        current_phase = new_phase
                        phase_bars = 0
                    
                    time.sleep(args.poll)
            
                # Policy cycle summary (inside for loop)
                summary = policy.get_summary(symbol, args.tf, profile_id)
                
                print()
                print("=" * 60)
                print(f"CYCLE {cycle_idx + 1}/{total_cycles} - PROOF_ROUTER_CLUSTER_POLICY SUMMARY")
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
            
                # ========== TRADE AUDIT V2 (inside for loop) ==========
                audit_enabled = getattr(args, "audit", False)
                if exchange_mode == "REAL_TESTNET" and success and audit_enabled:
                    try:
                        print(f"\n[TRADE_AUDIT_V2] Cycle {cycle_idx + 1}: Fetching order details + fees + position...")
                        
                        open_order_id = summary['open_order_id']
                        close_order_id = summary['close_order_id']
                        
                        # Position snapshot after CLOSE
                        pos_after = policy_gateway.get_position_snapshot(symbol)
                        pos_amt_after_close = abs(float(pos_after.get("position_qty", 0)))
                        
                        ndjson_event_sink({
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "event_type": "POSITION_SNAPSHOT_CLOSE",
                            "cycle_idx": cycle_idx + 1,
                            "symbol": symbol,
                            "pos_amt_now": pos_amt_after_close,
                            "entry_price": pos_after.get("entry_price"),
                        })
                        
                        # Fetch OPEN order
                        open_order = policy_gateway.get_order(symbol, open_order_id, max_wait_sec=10)
                        ndjson_event_sink({
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "event_type": "ORDER_FETCH_OPEN",
                            "cycle_idx": cycle_idx + 1,
                            "symbol": symbol,
                            "order_id": open_order_id,
                            "status": open_order.get("status"),
                            "executedQty": open_order.get("executedQty"),
                            "avgPrice": open_order.get("avgPrice"),
                            "success": open_order.get("success"),
                        })
                        
                        # Fetch CLOSE order
                        close_order = policy_gateway.get_order(symbol, close_order_id, max_wait_sec=10)
                        ndjson_event_sink({
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "event_type": "ORDER_FETCH_CLOSE",
                            "cycle_idx": cycle_idx + 1,
                            "symbol": symbol,
                            "order_id": close_order_id,
                            "status": close_order.get("status"),
                            "executedQty": close_order.get("executedQty"),
                            "avgPrice": close_order.get("avgPrice"),
                            "success": close_order.get("success"),
                        })
                        
                        # Fetch trades for fee extraction
                        open_trades = policy_gateway.get_user_trades(symbol, open_order_id)
                        close_trades = policy_gateway.get_user_trades(symbol, close_order_id)
                        
                        open_fee = open_trades.get("total_commission", 0)
                        close_fee = close_trades.get("total_commission", 0)
                        total_fee = open_fee + close_fee
                        fee_asset = open_trades.get("commission_asset", "USDT")
                        fee_available = open_trades.get("success", False) and close_trades.get("success", False)
                        
                        # Calculate PnL
                        entry_price = open_order.get("avgPrice", 0)
                        exit_price = close_order.get("avgPrice", 0)
                        qty = min(open_order.get("executedQty", 0), close_order.get("executedQty", 0))
                        
                        gross_pnl = qty * (exit_price - entry_price) if entry_price > 0 and exit_price > 0 else None
                        net_pnl = gross_pnl - total_fee if gross_pnl is not None and fee_available else None
                        
                        # Duration
                        duration_sec = summary.get('lag_sec_effective', 0)
                        
                        # Emit TRADE_AUDIT_V2_DONE
                        ndjson_event_sink({
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "event_type": "TRADE_AUDIT_V2_DONE",
                            "cycle_idx": cycle_idx + 1,
                            "symbol": symbol,
                            "timeframe": args.tf,
                            "open_order_id": open_order_id,
                            "close_order_id": close_order_id,
                            "close_order_id": close_order_id,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "qty": qty,
                            "gross_pnl_usdt": round(gross_pnl, 6) if gross_pnl else None,
                            "fee_usdt": round(total_fee, 6) if fee_available else "fee_unavailable",
                            "fee_open": open_fee,
                            "fee_close": close_fee,
                            "fee_asset": fee_asset,
                            "net_pnl_usdt": round(net_pnl, 6) if net_pnl is not None else None,
                            "pos_amt_after_close": pos_amt_after_close,
                            "duration_sec": duration_sec,
                            "status_open": open_order.get("status"),
                            "status_close": close_order.get("status"),
                        })
                        
                        # Print TRADE_AUDIT_V2_OK
                        open_status = open_order.get("status", "?")
                        close_status = close_order.get("status", "?")
                        gross_str = f"{gross_pnl:.6f}" if gross_pnl else "N/A"
                        fee_str = f"{total_fee:.6f}" if fee_available else "fee_unavailable"
                        net_str = f"{net_pnl:.6f}" if net_pnl is not None else "N/A"
                        
                        print(f"\nTRADE_AUDIT_V2_OK | entry={entry_price:.2f} exit={exit_price:.2f} qty={qty} gross={gross_str} fee={fee_str} net={net_str} pos_after={pos_amt_after_close} status_open={open_status} status_close={close_status}")
                        
                        if open_status != "FILLED" or close_status != "FILLED":
                            print(f"[TRADE_AUDIT_V2] WARNING: Orders not FILLED - open={open_status} close={close_status}")
                            ndjson_event_sink({
                                "ts": datetime.now(timezone.utc).isoformat(),
                                "event_type": "TRADE_AUDIT_V2_FAILED",
                                "reason": f"NOT_FILLED: open={open_status} close={close_status}",
                                "open_order_id": open_order_id,
                                "close_order_id": close_order_id,
                            })
                            
                    except Exception as e:
                        print(f"[TRADE_AUDIT_V2] ERROR: {e}")
                        ndjson_event_sink({
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "event_type": "TRADE_AUDIT_V2_FAILED",
                            "reason": str(e),
                        })
                
                # ========== CYCLE_DONE or CYCLE_TIMEOUT (end of for loop iteration) ==========
                if cycle_timed_out:
                    ndjson_event_sink({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "event_type": "CYCLE_TIMEOUT",
                        "cycle_idx": cycle_idx + 1,
                        "total_cycles": total_cycles,
                        "symbol": symbol,
                        "timeframe": args.tf,
                        "reason": timeout_reason,
                        "phase": current_phase,
                        "cycle_bars": cycle_bars,
                        "phase_bars": phase_bars,
                        "open_order_id": summary.get('open_order_id') if summary else None,
                        "close_order_id": summary.get('close_order_id') if summary else None,
                    })
                    
                    print(f"\nCYCLE_TIMEOUT | idx={cycle_idx + 1} reason={timeout_reason} phase={current_phase} bars={cycle_bars}/{args.cycle_timeout_bars}")
                else:
                    ndjson_event_sink({
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "event_type": "CYCLE_DONE",
                        "cycle_idx": cycle_idx + 1,
                        "total_cycles": total_cycles,
                        "symbol": symbol,
                        "timeframe": args.tf,
                        "open_order_id": summary['open_order_id'],
                        "close_order_id": summary['close_order_id'],
                        "eff_wait": summary['bars_waited_effective'],
                        "eff_lag": summary['lag_sec_effective'],
                        "residual_after": summary['residual_after'],
                        "exec_mode": exchange_mode.lower(),
                        "cycle_bars": cycle_bars,
                    })
                    
                    print(f"\nCYCLE_DONE | idx={cycle_idx + 1} open={summary['open_order_id']} close={summary['close_order_id']} eff_wait={summary['bars_waited_effective']} residual={summary['residual_after']} bars={cycle_bars} exec={exchange_mode.lower()}")
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
                handle_block_exit("SECRETS_MISSING", exit_code=1)
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
            # Lifecycle
            poll_order_sec=args.poll_order_sec,
            order_timeout_sec=args.order_timeout_sec,
            cancel_on_timeout=args.cancel_on_timeout,
            inject_fault=args.inject_order_fault,
            auto_export_on_block=args.auto_export_on_block,
            mainnet_allowlist=getattr(args, "mainnet_allowlist", None),
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
                cycle_idx=1,
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
    
    elif args.command == "report_cycles":
        # ========== REPORT_CYCLES COMMAND ==========
        # import sys (removed, global)
        from pathlib import Path
        from tezaver.matrix.live.cycle_events import (
            load_cycle_records,
            compute_aggregates,
            format_cycles_table,
            format_aggregates,
            CycleAlertLevel,
        )
        
        ndjson_path = Path("data/logs/live_events.ndjson")
        
        if not ndjson_path.exists():
            print(f"[REPORT_CYCLES] No NDJSON file found at {ndjson_path}")
            print()
            print("Runbook: Run a cycle first with:")
            print("  PYTHONPATH=src python -m tezaver.matrix.live.live_loop proof_router_cluster \\")
            print("    --real --tf 15m --exchange-mode DRY_RUN --exchange-enabled \\")
            print("    --hold-policy HOLD_NEXT_CLOSED --until-done --cycles 1")
        else:
            # Parse symbols from args
            symbols = [s.strip() for s in args.symbols.split(",")]
            symbol = symbols[0] if symbols else None
            timeframe = args.tf
            last_n = args.last
            only_filter = getattr(args, "only", None)
            
            print(f"[REPORT_CYCLES] Loading cycles from {ndjson_path}")
            print(f"[REPORT_CYCLES] Filter: symbol={symbol} tf={timeframe} last={last_n}")
            print()
            
            records = load_cycle_records(ndjson_path, symbol, timeframe, last_n)
            
            # Apply --only filter
            if only_filter:
                if only_filter == "WARN":
                    records = [r for r in records if r.alert_level in [CycleAlertLevel.WARN, CycleAlertLevel.BLOCK]]
                elif only_filter == "BLOCK":
                    records = [r for r in records if r.alert_level == CycleAlertLevel.BLOCK]
            
            if not records:
                print("No cycle records found matching filters.")
            else:
                # Print table
                print(format_cycles_table(records))
                
                # Print aggregates
                agg = compute_aggregates(records)
                print(format_aggregates(agg))
                
                # Print BLOCK reasons if any
                block_records = [r for r in records if r.alert_level == CycleAlertLevel.BLOCK]
                if block_records:
                    print()
                    print("⛔ BLOCK DETAILS:")
                    for r in block_records:
                        print(f"  Cycle {r.cycle_idx}: {', '.join(r.block_reasons)}")
                
                # Print WARN reasons if any
                warn_records = [r for r in records if r.alert_level == CycleAlertLevel.WARN]
                if warn_records:
                    print()
                    print("⚠️  WARN DETAILS:")
                    for r in warn_records:
                        print(f"  Cycle {r.cycle_idx}: {', '.join(r.warn_reasons)}")
                
                # Print equity curve and risk metrics if --print-metrics
                if getattr(args, "print_metrics", False):
                    from tezaver.matrix.live.cycle_events import (
                        compute_equity_curve,
                        compute_risk_metrics,
                        format_equity_table,
                        format_risk_metrics,
                    )
                    
                    equity_start = getattr(args, "equity_start", 100.0)
                    equity_points = compute_equity_curve(records, equity_start)
                    risk_metrics = compute_risk_metrics(records, equity_points, equity_start)
                    
                    print()
                    print("=== EQUITY CURVE ===")
                    print(format_equity_table(equity_points))
                    print(format_risk_metrics(risk_metrics))
                
                # Handle --cycle-idx --show-timeline
                cycle_idx_arg = getattr(args, "cycle_idx", None)
                show_timeline = getattr(args, "show_timeline", False)
                
                if cycle_idx_arg is not None and show_timeline:
                    from tezaver.matrix.live.cycle_events import (
                        get_cycle_events,
                        format_cycle_timeline,
                    )
                    import json as json_module
                    
                    timeline_events = get_cycle_events(ndjson_path, cycle_idx_arg, symbol)
                    
                    # Apply --only-types filter
                    only_types = getattr(args, "only_types", None)
                    if only_types:
                        type_list = [t.strip() for t in only_types.split(",")]
                        timeline_events = [e for e in timeline_events if e.get("event_type") in type_list]
                    
                    # Apply --grep filter
                    grep_text = getattr(args, "grep", None)
                    if grep_text:
                        filtered = []
                        for e in timeline_events:
                            event_str = json_module.dumps(e, default=str)
                            if grep_text.lower() in event_str.lower():
                                filtered.append(e)
                        timeline_events = filtered
                    
                    # Output
                    raw_json_mode = getattr(args, "raw_json", False)
                    if raw_json_mode:
                        print(f"\n=== CYCLE {cycle_idx_arg} RAW EVENTS ({len(timeline_events)}) ===")
                        for e in timeline_events:
                            print(json_module.dumps(e, default=str))
                    else:
                        print(format_cycle_timeline(timeline_events, cycle_idx_arg))
                
                # Handle --export-json
                export_json_path = getattr(args, "export_json", None)
                if export_json_path:
                    from tezaver.matrix.live.cycle_events import export_cycles_json
                    
                    export_path = Path(export_json_path)
                    export_cycles_json(records, export_path)
                    print(f"\n[EXPORT] Cycles exported to {export_path}")
                
                # Handle --export-bundle
                export_bundle = getattr(args, "export_bundle", False)
                cycle_idx_for_bundle = getattr(args, "cycle_idx", None)
                
                if export_bundle:
                    if cycle_idx_for_bundle is None:
                        print("[ERROR] --export-bundle requires --cycle-idx")
                        sys.exit(1)
                    
                    from tezaver.matrix.live.cycle_events import (
                        IncidentBundleSpec,
                        build_incident_bundle,
                    )
                    
                    # Build spec
                    only_types_list = None
                    only_types_str = getattr(args, "only_types", None)
                    if only_types_str:
                        only_types_list = [t.strip() for t in only_types_str.split(",")]
                    
                    spec = IncidentBundleSpec(
                        symbol=symbol,
                        timeframe=timeframe,
                        cycle_idx=cycle_idx_for_bundle,
                        ndjson_path=str(ndjson_path),
                        equity_start=getattr(args, "equity_start", 100.0),
                        out_dir=getattr(args, "out_dir", "data/incidents"),
                        include_event_types=only_types_list,
                        grep=getattr(args, "grep", None),
                        only_relevant=getattr(args, "only_relevant", False),
                    )
                    
                    result = build_incident_bundle(spec)
                    
                    if result["success"]:
                        print(f"\nINCIDENT_BUNDLE_OK | path={result['bundle_path']} files={len(result['files'])} alert={result['alert']}")
                        for f in result['files']:
                            print(f"  - {f}")
                    else:
                        print(f"[ERROR] Bundle export failed: {result['error']}")
                        sys.exit(1)
                
                # ========== AUTO-INCIDENT EXPORT ==========
                auto_incident_on = getattr(args, "auto_incident_on", "BLOCK")
                
                if auto_incident_on != "OFF":
                    # Filter records by auto-incident alert level
                    auto_records = []
                    if auto_incident_on == "BLOCK":
                        auto_records = [r for r in records if r.alert_level == CycleAlertLevel.BLOCK]
                    elif auto_incident_on == "WARN":
                        auto_records = [r for r in records if r.alert_level in [CycleAlertLevel.WARN, CycleAlertLevel.BLOCK]]
                    
                    # Limit to max N
                    auto_incident_max = getattr(args, "auto_incident_max", 1)
                    auto_records = auto_records[:auto_incident_max]
                    
                    if auto_records:
                        print(f"\n[AUTO_INCIDENT] Found {len(auto_records)} cycles matching {auto_incident_on}, exporting bundles...")
                        
                        from tezaver.matrix.live.cycle_events import (
                            IncidentBundleSpec,
                            build_incident_bundle,
                        )
                        
                        auto_out_dir = getattr(args, "auto_incident_out_dir", "data/incidents")
                        auto_only_relevant = getattr(args, "auto_incident_only_relevant", True)
                        
                        for r in auto_records:
                            try:
                                spec = IncidentBundleSpec(
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    cycle_idx=r.cycle_idx,
                                    ndjson_path=str(ndjson_path),
                                    equity_start=getattr(args, "equity_start", 100.0),
                                    out_dir=auto_out_dir,
                                    only_relevant=auto_only_relevant,
                                )
                                
                                result = build_incident_bundle(spec)
                                
                                if result["success"]:
                                    print(f"AUTO_INCIDENT_OK | cycle_idx={r.cycle_idx} path={result['bundle_path']} alert={result['alert']} files={len(result['files'])}")
                                    
                                    # Emit telemetry
                                    emit_incident_bundle_telemetry(
                                        symbol=symbol,
                                        timeframe=timeframe,
                                        cycle_idx=r.cycle_idx,
                                        alert_level=result['alert'],
                                        out_path=result['bundle_path'],
                                        files_count=len(result['files']),
                                    )
                                else:
                                    print(f"AUTO_INCIDENT_ERR | cycle_idx={r.cycle_idx} error={result['error']}")
                            except Exception as e:
                                print(f"AUTO_INCIDENT_ERR | cycle_idx={r.cycle_idx} error={str(e)}")
                
                # Exit code 2 if BLOCK exists
                if agg.get("block_count", 0) > 0:
                    print()
                    print("❌ Exit code 2: BLOCK violations found")
                    sys.exit(2)
    
    elif args.command == "reconcile":
        # Restart Reconciliation Command
        import json
        from pathlib import Path
        from tezaver.matrix.live.live_reconcile import ReconcileService
        from tezaver.matrix.live.strategy_signal import PositionStateStore
        
        print("[RECONCILE] Starting restart reconciliation...")
        
        # Parse symbols
        symbols = [s.strip() for s in args.symbols.split(",")]
        
        # Setup NDJSON sink
        ndjson_path = Path("data/logs/live_events.ndjson")
        ndjson_path.parent.mkdir(parents=True, exist_ok=True)
        
        def ndjson_sink(event: Dict[str, Any]):
            with open(ndjson_path, "a") as f:
                f.write(json.dumps(event, default=str) + "\n")
        
        # Create gateway if REAL mode
        gateway = None
        exchange_mode = getattr(args, "exchange_mode", "DRY_RUN")
        if exchange_mode.startswith("REAL"):
            from tezaver.matrix.live.live_gateway import BinanceTestnetGateway
            gateway = BinanceTestnetGateway()
            print(f"[RECONCILE] Using {exchange_mode} gateway")
        else:
            print(f"[RECONCILE] {exchange_mode} mode - local state only")
        
        # Create position store
        position_store = PositionStateStore(event_sink=ndjson_sink)
        
        # Create reconcile service
        service = ReconcileService(
            gateway=gateway,
            position_store=position_store,
            event_sink=ndjson_sink,
            exchange_mode=exchange_mode,
            armed=getattr(args, "armed", False),
            exchange_enabled=getattr(args, "exchange_enabled", False),
        )
        
        # Load persisted state
        print("[RECONCILE] Loading persisted state...")
        load_result = service.load_persisted_state()
        print(f"[RECONCILE] Loaded: {load_result['fingerprints_loaded']} fingerprints, {load_result['positions_loaded']} positions")
        if load_result["errors"]:
            print(f"[RECONCILE] Load errors: {load_result['errors']}")
        
        # Reconcile cells
        cells = [
            {"symbol": s, "timeframe": args.tf, "profile_id": f"{s}_{args.tf}_policy"}
            for s in symbols
        ]
        
        print(f"[RECONCILE] Reconciling {len(cells)} cells...")
        result = service.reconcile_cells(cells)
        
        # Print results
        print()
        print("=" * 60)
        print("RECONCILE RESULT")
        print("=" * 60)
        print(f"Status: {'✅ OK' if result.ok else '⚠️ WARNINGS'}")
        print(f"Cells: {len(result.per_cell)}")
        
        # Export incident bundle on reconcile failure if enabled
        if not result.ok:
            from tezaver.matrix.live.incident_bundle import maybe_export_on_block
            maybe_export_on_block(
                reason=f"RECON_FATAL:warnings={len(result.warnings)},paused={len(result.paused_cells)}",
                enabled=getattr(args, "auto_export_on_block", False),
            )
        
        if result.warnings:
            print(f"Warnings: {len(result.warnings)}")
            for w in result.warnings[:10]:
                print(f"  - {w}")
        
        print()
        print("Per-Cell Summary:")
        for cell in result.per_cell:
            status = "✅" if cell.ok else "⚠️"
            print(f"  {status} {cell.cell_id}")
            print(f"      Exchange Pos: {cell.pos_amt_exchange}")
            print(f"      Local Before: {cell.pos_state_local_before} → After: {cell.pos_state_local_after}")
            print(f"      Actions: {cell.actions_taken}")
            if cell.warnings:
                for w in cell.warnings:
                    print(f"      ⚠️ {w}")
        
        # Save updated state
        print()
        print("[RECONCILE] Saving state...")
        save_result = service.save_persisted_state()
        print(f"[RECONCILE] Saved: {save_result['fingerprints_saved']} fingerprints, {save_result['positions_saved']} positions")
        
        print()
        print("[RECONCILE] Done.")


if __name__ == "__main__":
    main()
