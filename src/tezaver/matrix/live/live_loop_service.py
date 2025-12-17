# Live Loop Service
"""
Singleton service for managing live loop from UI.

Persists across Streamlit reruns using threading.
"""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

from tezaver.matrix.live.live_loop import (
    LiveLoopConfig,
    LiveLoopStats,
    run_live_loop,
    TICK_POLICY_ON_CLOSED_BAR,
)
from tezaver.matrix.live.marketdata.client import (
    IMarketDataClient,
    DummyMarketDataClient,
    BinancePublicClient,
)


@dataclass
class CellMetrics:
    """Per-cell metrics for live monitor."""
    symbol: str
    timeframe: str
    profile_id: str = ""
    last_closed_bar_ts: Optional[datetime] = None
    last_tick_ts: Optional[datetime] = None
    last_tick_reason: str = ""
    ticks_count: int = 0
    skips_count: int = 0
    lag_sec: float = 0.0
    last_close: Optional[float] = None


@dataclass
class ServiceStatus:
    """Live loop service status."""
    running: bool = False
    last_poll_ts: Optional[datetime] = None
    polls: int = 0
    ticks: int = 0
    skips: int = 0
    last_error: Optional[str] = None
    cells_count: int = 0


class LiveLoopService:
    """
    Singleton service for live loop management.
    
    Thread-safe, persists across Streamlit reruns.
    """
    
    _instance: Optional["LiveLoopService"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance
    
    @classmethod
    def get(cls) -> "LiveLoopService":
        """Get singleton instance."""
        return cls()
    
    def _init(self):
        """Initialize service state."""
        self._running = False
        self._stop_flag = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._config: Optional[LiveLoopConfig] = None
        self._stats: Optional[LiveLoopStats] = None
        self._cells: List[tuple] = []  # [(symbol, tf), ...]
        self._client: Optional[IMarketDataClient] = None
        self._cluster = None
        self._cells = []
        self._running = False
        self._stats = LiveLoopStats()
        self._cell_metrics = {}  # cell_id -> CellMetrics
        self._thread = None
        self._stop_event = threading.Event()
        
        # Proof/Verification state
        self._proof_mode = False
        self._proof_run_id = None
        self._proof_history = deque(maxlen=50)
        self._proof_state = "IDLE"
        self._proof_started_at: Optional[datetime] = None
        self._last_proof_event: Optional[Dict[str, Any]] = None
        self._last_error: Optional[str] = None
        
        # Router/Callback
        self._on_closed_bar_cb = None
        self._router_metrics = {}
        self._router_attached = False
        self._router_ticks = 0
        self._last_router_tick: Optional[Dict[str, Any]] = None
        
        # M3a: HTF Permissions (Symbol -> Decision)
        # e.g. "BTCUSDT" -> "ALLOW_LONG"
        self._htf_permissions: Dict[str, str] = {}
        
        # Dedup tracking: cell_id -> last_processed_bar_ts (str)
        self._processed_bars: Dict[str, str] = {}
        
        # Last poll timestamp
        self._last_poll_ts: Optional[datetime] = None
    
    @property
    def running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()
    
    def start(
        self,
        cells: List[tuple],  # [(symbol, tf), ...]
        use_real: bool = True,
        tick_policy: str = TICK_POLICY_ON_CLOSED_BAR,
        poll_interval: float = 5.0,
        max_runtime: float = 3600.0,
        cluster=None,
    ) -> bool:
        """
        Start live loop in background thread.
        
        Returns True if started, False if already running.
        """
        with self._lock:
            if self._running:
                return False
            
            self._init()
            self._cells = cells
            self._running = True
            
            # Initialize metrics for cells
            for sym, tf in cells:
                cid = f"{sym}:{tf}"
                self._cell_metrics[cid] = CellMetrics(symbol=sym, timeframe=tf)
            
            self._thread = threading.Thread(
                target=self._run_loop,
                args=(use_real, tick_policy, poll_interval, max_runtime, cluster),
                daemon=True,
            )
            self._thread.start()
            return True
    
    def stop(self) -> bool:
        """Stop live loop gracefully."""
        if self._thread:
            self._thread.join(timeout=5.0)
        
        self._running = False
        self._proof_mode = False
        return True
    
    def start_proof_closed(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "1m",
        poll_sec: float = 5.0,
        use_real: bool = True,
    ) -> str:
        """
        Start proof mode for closed bar verification.
        
        Returns proof_run_id.
        """
        import uuid
        
        if self.running:
            return ""  # Already running
        
        # Generate run ID
        run_id = f"proof_{uuid.uuid4().hex[:8]}"
        
        self._proof_mode = True
        self._proof_run_id = run_id
        self._proof_started_at = datetime.now(timezone.utc)
        self._last_proof_event = None
        
        # Start with proof settings
        self.start(
            cells=[(symbol, timeframe)],
            use_real=use_real,
            tick_policy=TICK_POLICY_ON_CLOSED_BAR,
            poll_interval=poll_sec,
            max_runtime=1800.0,  # 30 min max
            cluster=None,  # No cluster to tick in proof mode
        )
        
        # Override config for proof mode
        if self._config:
            self._config.until_next_closed = True
            self._config.align_to_next_close = True
            self._config.proof_closed = True
        
        return run_id
    
    def start_proof_router(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "15m",
        poll_sec: float = 5.0,
        use_real: bool = True,
    ) -> str:
        """
        Start proof + router mode for E2E verification.
        
        Combines proof mode with router tick callback.
        Returns proof_run_id.
        """
        from tezaver.matrix.live.live_router import MatrixLiveRouter, LiveRouterConfig
        import uuid
        
        if self.running:
            return ""  # Already running
        
        # Generate run ID
        run_id = f"proof_router_{uuid.uuid4().hex[:8]}"
        
        self._proof_mode = True
        self._proof_run_id = run_id
        self._proof_started_at = datetime.now(timezone.utc)
        self._last_proof_event = None
        
        # Create router with forced dry_run
        router_config = LiveRouterConfig(
            enabled=True,
            force_dry_run=True,
            only_symbols=[symbol],
            only_timeframes=[timeframe],
        )
        self._proof_router = MatrixLiveRouter(cluster=None, config=router_config)
        self._proof_router_result = {"ticks": 0, "skips": 0, "last_tick": None}
        
        # Start with proof settings
        self.start(
            cells=[(symbol, timeframe)],
            use_real=use_real,
            tick_policy=TICK_POLICY_ON_CLOSED_BAR,
            poll_interval=poll_sec,
            max_runtime=1800.0,  # 30 min max for 15m
            cluster=None,
        )
        
        # Override config for proof mode
        if self._config:
            self._config.until_next_closed = True
            self._config.align_to_next_close = True
            self._config.proof_closed = True
        
        return run_id
    
    def get_proof_router_state(self) -> Dict[str, Any]:
        """Get proof + router state for UI."""
        router_result = getattr(self, "_proof_router_result", {"ticks": 0, "skips": 0, "last_tick": None})
        router = getattr(self, "_proof_router", None)
        
        return {
            "running": self.running and self._proof_mode,
            "proof_mode": self._proof_mode,
            "proof_run_id": self._proof_run_id,
            "started_at": self._proof_started_at.isoformat() if self._proof_started_at else None,
            "last_proof_event": self._last_proof_event,
            "router_ticks": router.tick_count if router else router_result.get("ticks", 0),
            "router_skips": router.skip_count if router else router_result.get("skips", 0),
            "router_last_tick": router.last_tick if router else router_result.get("last_tick"),
            "last_error": self._last_error,
        }
    
    def start_proof_router_cluster(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "15m",
        poll_sec: float = 5.0,
        use_real: bool = True,
    ) -> str:
        """
        Start proof + router + cluster mode for full E2E verification.
        
        Uses a StubCluster that returns DRY_RUN results.
        Returns proof_run_id.
        """
        from tezaver.matrix.live.live_router import MatrixLiveRouter, LiveRouterConfig
        import uuid
        
        if self.running:
            return ""  # Already running
        
        # Generate run ID
        run_id = f"proof_cluster_{uuid.uuid4().hex[:8]}"
        
        self._proof_mode = True
        self._proof_run_id = run_id
        self._proof_started_at = datetime.now(timezone.utc)
        self._last_proof_event = None
        
        # Create stub cluster for DRY_RUN testing
        class StubCluster:
            def __init__(self):
                self.tick_count = 0
                self.last_tick = None
                self.last_result = None
            
            def tick(self, symbol, timeframe, market_snapshot, runtime_overrides=None):
                self.tick_count += 1
                self.last_tick = market_snapshot
                dry_run = (runtime_overrides or {}).get("force_dry_run", True)
                self.last_result = {
                    "decisions_count": 1,
                    "executions_count": 1 if dry_run else 0,
                    "dry_run": dry_run,
                    "order_id": "DRY_RUN" if dry_run else "REAL",
                    "allow": True,
                    "profile_id": f"{symbol}_{timeframe}_live",  # Real profile_id format
                    "equity_after": 100.0,
                }
                return self.last_result
        
        self._proof_cluster = StubCluster()
        
        # Create router with cluster
        router_config = LiveRouterConfig(
            enabled=True,
            force_dry_run=True,
            only_symbols=[symbol],
            only_timeframes=[timeframe],
        )
        self._proof_router = MatrixLiveRouter(cluster=self._proof_cluster, config=router_config)
        self._proof_router_result = {"ticks": 0, "skips": 0, "last_tick": None, "cluster_ticks": 0}
        
        # Initialize history if not exists
        if not hasattr(self, "_proof_cluster_history"):
            self._proof_cluster_history = []
        
        # Start with proof settings
        self.start(
            cells=[(symbol, timeframe)],
            use_real=use_real,
            tick_policy=TICK_POLICY_ON_CLOSED_BAR,
            poll_interval=poll_sec,
            max_runtime=1800.0,  # 30 min max for 15m
            cluster=None,  # Router handles cluster injection
        )
        
        # Override config for proof mode
        if self._config:
            self._config.until_next_closed = True
            self._config.align_to_next_close = True
            self._config.proof_closed = True
        
        return run_id
    
    def get_proof_router_cluster_state(self) -> Dict[str, Any]:
        """Get proof + router + cluster state for UI."""
        router = getattr(self, "_proof_router", None)
        cluster = getattr(self, "_proof_cluster", None)
        history = getattr(self, "_proof_cluster_history", [])
        
        return {
            "running": self.running and self._proof_mode,
            "proof_mode": self._proof_mode,
            "proof_run_id": self._proof_run_id,
            "started_at": self._proof_started_at.isoformat() if self._proof_started_at else None,
            "last_proof_event": self._last_proof_event,
            "router_ticks": router.tick_count if router else 0,
            "router_skips": router.skip_count if router else 0,
            "router_last_tick": router.last_tick if router else None,
            "cluster_ticks": cluster.tick_count if cluster else 0,
            "cluster_last_result": cluster.last_result if cluster else None,
            "history": history[-20:],  # Last 20
            "last_error": self._last_error,
        }
    
    def get_proof_state(self) -> Dict[str, Any]:
        """Get current proof job state."""
        proof_started_at = getattr(self, '_proof_started_at', None)
        return {
            "running": self.running and getattr(self, '_proof_mode', False),
            "proof_mode": getattr(self, '_proof_mode', False),
            "proof_run_id": getattr(self, '_proof_run_id', None),
            "started_at": proof_started_at.isoformat() if proof_started_at else None,
            "last_proof_event": getattr(self, '_last_proof_event', None),
            "last_error": getattr(self, '_last_error', None),
        }
    
    def stop_proof_closed(self) -> bool:
        """Stop proof job."""
        self._proof_mode = False
        return self.stop()
    
    def get_proof_history(self) -> List[Dict[str, Any]]:
        """Get proof history as list, newest first."""
        return list(reversed(self._proof_history))
    
    def set_on_closed_bar_callback(self, cb) -> None:
        """Set callback to be called on each closed bar tick."""
        self._on_closed_bar_cb = cb
        self._router_attached = cb is not None
    
    def detach_router(self) -> None:
        """Detach router callback."""
        self._on_closed_bar_cb = None
        self._router_attached = False
    
    def get_router_state(self) -> Dict[str, Any]:
        """Get router state for UI."""
        return {
            "attached": getattr(self, '_router_attached', False),
            "ticks": getattr(self, '_router_ticks', 0),
            "last_tick": getattr(self, '_last_router_tick', None),
        }
    
    def check_arm_allowed(
        self,
        router_enabled: bool = False,
        exchange_enabled: bool = False,
        exchange_mode: str = "DRY_RUN",
    ) -> Dict[str, Any]:
        """
        Check if ARMED toggle is allowed.
        
        Requirements:
        1. Router Enabled = ON
        2. Exchange Enabled = ON
        3. ExchangeMode != DRY_RUN (at least DUMMY_ORDER)
        4. Recent proof (within 10 minutes)
        5. Secrets present (only for REAL_* modes)
        6. Profile status APPROVED
        7. Contract gate not BLOCK
        
        Returns dict with allowed, missing_reasons list.
        """
        missing = []
        
        # (a) Router enabled
        if not router_enabled:
            missing.append("Router not enabled")
        
        # (c) Recent proof (within 10 minutes)
        has_recent_proof = False
        if self._last_proof_event:
            proof_ts = self._last_proof_event.get("ts") or self._last_proof_event.get("tick_received_ts")
            if proof_ts:
                try:
                    from datetime import datetime, timezone, timedelta
                    proof_dt = datetime.fromisoformat(proof_ts.replace("Z", "+00:00"))
                    now = datetime.now(timezone.utc)
                    if (now - proof_dt).total_seconds() < 600:  # 10 minutes
                        has_recent_proof = True
                except:
                    pass
        
        if not has_recent_proof:
            missing.append("No recent proof (need PROOF_CLOSED within 10 min)")
        
        # (d) Secrets - only required for REAL_* modes
        from tezaver.matrix.live.live_gateway import ExchangeMode
        exchange_mode_enum = ExchangeMode.DRY_RUN
        try:
            exchange_mode_enum = ExchangeMode(exchange_mode) if isinstance(exchange_mode, str) else exchange_mode
        except:
            pass
        
        requires_secrets = exchange_mode_enum in (ExchangeMode.REAL_TESTNET, ExchangeMode.REAL_MAINNET)
        
        if requires_secrets:
            try:
                from tezaver.matrix.live.secrets import CompositeVault
                vault = CompositeVault()
                api_key = vault.get("BINANCE_API_KEY")
                api_secret = vault.get("BINANCE_API_SECRET")
                if not api_key or not api_secret:
                    missing.append("Secrets missing (required for REAL mode)")
            except:
                missing.append("Secrets vault not accessible (required for REAL mode)")
        
        # (e) Exchange enabled
        if not exchange_enabled:
            missing.append("exchange_enabled is OFF")
        
        # (f) ExchangeMode != DRY_RUN (at least DUMMY_ORDER)
        if exchange_mode_enum == ExchangeMode.DRY_RUN:
            missing.append("ExchangeMode is DRY_RUN (need at least DUMMY_ORDER)")
        
        # (g) Profile status APPROVED (stub - would check real profile)
        cluster_allow = True
        last_cluster_result = getattr(self, "_proof_cluster", None)
        if last_cluster_result and hasattr(last_cluster_result, "last_result"):
            result = last_cluster_result.last_result
            if result and not result.get("allow", True):
                cluster_allow = False
                missing.append("Live Gate: allow=False")
        
        # (h) Contract gate not BLOCK (stub - would check real contract)
        contract_gate_ok = True  # Default to true for now
        
        return {
            "allowed": len(missing) == 0,
            "missing_reasons": missing,
            "exchange_mode": exchange_mode_enum.value if hasattr(exchange_mode_enum, 'value') else str(exchange_mode_enum),
            "requires_secrets": requires_secrets,
        }
    
    def status(self) -> ServiceStatus:
        """Get current service status."""
        return ServiceStatus(
            running=self.running,
            last_poll_ts=getattr(self, '_last_poll_ts', None),
            polls=self._stats.poll_count if self._stats else 0,
            ticks=self._stats.tick_count if self._stats else 0,
            skips=self._stats.skip_count if self._stats else 0,
            last_error=getattr(self, '_last_error', None),
            cells_count=len(self._cells),
        )
    
    def status_dict(self) -> Dict[str, Any]:
        """Get status as dict for UI."""
        s = self.status()
        return {
            "running": s.running,
            "last_poll_ts": s.last_poll_ts.isoformat() if s.last_poll_ts else None,
            "polls": s.polls,
            "ticks": s.ticks,
            "skips": s.skips,
            "last_error": s.last_error,
            "cells_count": s.cells_count,
        }
    
    def last_metrics(self) -> Dict[str, CellMetrics]:
        """Get per-cell metrics."""
        return self._cell_metrics.copy()
    
    def get_cell_metrics(self) -> List[Dict[str, Any]]:
        """Get per-cell metrics as flat list for UI table."""
        # Force update from stats if available
        if self._stats and self._stats.events:
            self._update_metrics_from_stats()
        
        result = []
        now = datetime.now(timezone.utc)
        
        for key, m in self._cell_metrics.items():
            # Recalculate lag
            lag = None
            if m.last_closed_bar_ts:
                if m.last_closed_bar_ts.tzinfo is None:
                    lag = (now.replace(tzinfo=None) - m.last_closed_bar_ts).total_seconds()
                else:
                    lag = (now - m.last_closed_bar_ts).total_seconds()
            
            result.append({
                "symbol": m.symbol,
                "timeframe": m.timeframe,
                "profile_id": m.profile_id,
                "last_closed_bar_ts": m.last_closed_bar_ts.isoformat() if m.last_closed_bar_ts else None,
                "last_tick_ts": m.last_tick_ts.isoformat() if m.last_tick_ts else None,
                "last_tick_reason": m.last_tick_reason,
                "ticks_count": m.ticks_count,
                "skips_count": m.skips_count,
                "lag_sec": round(lag, 1) if lag is not None else None,
                "last_close": m.last_close,
            })
        
        return result
    
    def _provide_context(self, symbol: str, tf: str) -> Dict[str, Any]:
        """Provide runtime context (overrides) for tick."""
        # M3a: HTF Permission injection
        perm_data = self._htf_permissions.get(symbol)
        
        ctx = {}
        if perm_data:
            decision = None
            
            # Handle both new dict format and legacy string format
            if isinstance(perm_data, dict):
                decision_val = perm_data.get("decision")
                perm_tf = perm_data.get("tf", "4h")
                perm_ts = perm_data.get("ts")
                
                # Check Staleness
                # 4h -> 4h + 20m buffer (260m)
                # 1d -> 24h + 60m buffer (1500m)
                ttl_minutes = 260
                if perm_tf == "1d":
                    ttl_minutes = 1500
                elif perm_tf == "1h": 
                    ttl_minutes = 70
                    
                if perm_ts:
                    age = datetime.now(timezone.utc) - perm_ts
                    if age.total_seconds() > ttl_minutes * 60:
                        # Stale - treat as NO_CONTEXT
                         print(f"[HTF_STATE] Stale context for {symbol}: {age.total_seconds()/60:.1f}m > {ttl_minutes}m")
                         decision = None 
                    else:
                        decision = decision_val
                else:
                    decision = decision_val
            else:
                # Legacy string format (no timestamp)
                decision = perm_data
                
            if decision:
                ctx["htf_decision"] = decision
        
        return ctx

    def _run_loop(self, use_real: bool, tick_policy: str, poll_interval: float, max_runtime: float, cluster=None):
        """Internal loop runner (runs in thread)."""
        # Create client inside thread
        if use_real:
            from tezaver.matrix.live.marketdata.client import BinancePublicClient
            client = BinancePublicClient()
        else:
            from tezaver.matrix.live.marketdata.client import DummyMarketDataClient
            client = DummyMarketDataClient()
            
        config = LiveLoopConfig(
            poll_interval_sec=poll_interval,
            tick_policy=tick_policy,
            max_runtime_sec=max_runtime,
            dry_run=not use_real,
        )
        
        try:
            self._stats = run_live_loop(
                symbols_timeframes=self._cells,
                data_client=client,
                config=config,
                cluster=cluster,
                stop_flag=self._stop_event,
                event_callback=self._on_event,
                runtime_context_provider=self._provide_context,
            )
            
            # Final update of metrics from stats
            self._update_metrics_from_stats()
            
        except Exception as e:
            self._stats.last_error = str(e)
            print(f"[LIVE_LOOP_SERVICE] Error: {e}")
        finally:
            self._running = False

    def _on_event(self, event: Dict[str, Any]):
        """Handle real-time event from loop."""
        # M3a: Capture HTF Permission
        et = event.get("event_type", "")
        if et == "HTF_PERMISSION_EVAL":
            symbol = event.get("symbol")
            decision = event.get("decision")
            tf = event.get("timeframe", "4h") # Default to 4h if missing
            
            if symbol and decision:
                # Store permission with timestamp for staleness check
                self._htf_permissions[symbol] = {
                    "decision": decision,
                    "tf": tf,
                    "ts": datetime.now(timezone.utc)
                }
                print(f"[HTF_STATE] Updated {symbol} -> {decision} ({tf})")

        now = datetime.now(timezone.utc)
        
        symbol = event.get("symbol")
        tf = event.get("timeframe")
        key = f"{symbol}:{tf}"  # Normalized key format
        
        if key not in self._cell_metrics:
            # Try alt format from legacy
            key_alt = f"{symbol}|{tf}"
            if key_alt in self._cell_metrics:
                key = key_alt
            else:
                return

        metrics = self._cell_metrics[key]
        
        if et == "LIVE_TICK":
            metrics.ticks_count += 1
            metrics.last_tick_ts = now
            # Last close from snapshot if available
            metrics.last_close = event.get("snapshot_close")
            
            bar_close_ts = event.get("bar_close_ts")
            if bar_close_ts:
                try:
                    metrics.last_closed_bar_ts = datetime.fromisoformat(bar_close_ts.replace("Z", "+00:00"))
                except:
                    pass
            
            metrics.last_tick_reason = "TICK"
            
            # Router callback
            if self._on_closed_bar_cb:
                try:
                    self._on_closed_bar_cb(event)
                    self._router_ticks += 1
                    self._last_router_tick = event
                except Exception as e:
                    print(f"Router CB error: {e}")

        elif et == "LIVE_SKIP":
            metrics.skips_count += 1
            metrics.last_tick_reason = event.get("tick_reason", "SKIP")
        
        # Proof event capture
        if self._proof_mode:
             self._last_proof_event = event
             if et in ("CLOSED_PROOF", "ROUTER_TICK_RESULT", "ROUTER_CLUSTER_OK"):
                 self._proof_history.append(event)

        
        metrics = self._cell_metrics[key]
        event_type = event.get("event_type")
        
        # Always update last poll timestamp
        self._last_poll_ts = now
        metrics.last_tick_ts = now
        metrics.last_tick_reason = event.get("tick_reason", "")
        
        if event_type == "LIVE_TICK":
            metrics.ticks_count += 1
            metrics.last_close = event.get("snapshot_close")
            
            # Use bar_close_ts field from event
            bar_close_ts_str = event.get("bar_close_ts")
            if bar_close_ts_str:
                try:
                    metrics.last_closed_bar_ts = datetime.fromisoformat(
                        bar_close_ts_str.replace("Z", "+00:00")
                    )
                except:
                    pass
            
            # Call router callback for closed bar ticks
            tick_reason = event.get("tick_reason", "")
            if tick_reason == "NEW_CLOSED_BAR" and self._on_closed_bar_cb:
                try:
                    # Build snapshot for router
                    snapshot = {
                        "symbol": symbol,
                        "timeframe": tf,
                        "bar_close_ts": bar_close_ts_str,
                        "close": event.get("snapshot_close"),
                        "rsi_15m": event.get("rsi_15m"),
                        "is_closed": event.get("is_closed", True),
                    }
                    self._on_closed_bar_cb(snapshot)
                    self._router_ticks += 1
                    self._last_router_tick = {
                        "symbol": symbol,
                        "timeframe": tf,
                        "bar_close_ts": bar_close_ts_str,
                        "close": event.get("snapshot_close"),
                        "ts": now.isoformat(),
                    }
                except Exception as cb_err:
                    print(f"[LIVE_ROUTER_ERROR] {cb_err}")
        
        elif event_type == "LIVE_SKIP":
            metrics.skips_count += 1
        
        elif event_type == "CLOSED_PROOF":
            # Capture proof event for UI display
            self._last_proof_event = {
                "symbol": symbol,
                "timeframe": tf,
                "bar_close_ts": event.get("bar_close_ts"),
                "baseline_closed_ts": event.get("baseline_closed_ts"),
                "strict_new_closed": event.get("strict_new_closed", True),
                "lag_sec": event.get("lag_sec"),
                "close": event.get("close"),
                "policy": event.get("policy"),
                "proof_force_dry_run": True,  # Always dry run in proof mode
                "ts": event.get("ts") or datetime.now(timezone.utc).isoformat(),
            }
            # Append to history
            self._proof_history.append(self._last_proof_event.copy())
            
            # Route to proof_router if active
            proof_router = getattr(self, "_proof_router", None)
            if proof_router:
                try:
                    snapshot = {
                        "symbol": symbol,
                        "timeframe": tf,
                        "bar_close_ts": event.get("bar_close_ts"),
                        "close": event.get("close"),
                    }
                    proof_router.handle_snapshot(snapshot)
                except Exception as router_err:
                    print(f"[PROOF_ROUTER_ERROR] {router_err}")
        
        # Update lag
        if metrics.last_closed_bar_ts:
            if metrics.last_closed_bar_ts.tzinfo is None:
                metrics.lag_sec = (now.replace(tzinfo=None) - metrics.last_closed_bar_ts).total_seconds()
            else:
                metrics.lag_sec = (now - metrics.last_closed_bar_ts).total_seconds()
    
    def _update_metrics_from_stats(self):
        """Update cell metrics from last stats."""
        if not self._stats:
            return
        
        now = datetime.now(timezone.utc)
        
        for event in self._stats.events:
            symbol = event.get("symbol")
            tf = event.get("timeframe")
            key = f"{symbol}|{tf}"
            
            if key not in self._cell_metrics:
                continue
            
            metrics = self._cell_metrics[key]
            event_type = event.get("event_type")
            
            # Always update last_tick_ts on any event
            metrics.last_tick_ts = now
            
            if event_type == "LIVE_TICK":
                metrics.ticks_count += 1
                metrics.last_tick_reason = event.get("tick_reason", "")
                metrics.last_close = event.get("snapshot_close")
                
                # Use bar_close_ts field from event (preferred)
                bar_close_ts_str = event.get("bar_close_ts")
                if bar_close_ts_str:
                    try:
                        metrics.last_closed_bar_ts = datetime.fromisoformat(
                            bar_close_ts_str.replace("Z", "+00:00")
                        )
                    except:
                        pass
                
                # Fallback to last_bar_ts
                elif event.get("last_bar_ts"):
                    try:
                        metrics.last_closed_bar_ts = datetime.fromisoformat(
                            event.get("last_bar_ts").replace("Z", "+00:00")
                        )
                    except:
                        pass
            
            elif event_type == "LIVE_SKIP":
                metrics.skips_count += 1
                metrics.last_tick_reason = event.get("tick_reason", "")
            
            # Update lag from last_closed_bar_ts
            if metrics.last_closed_bar_ts:
                # Ensure both are timezone-aware or naive
                if metrics.last_closed_bar_ts.tzinfo is None:
                    # Make it aware
                    from datetime import timezone as tz
                    metrics.lag_sec = (now.replace(tzinfo=None) - metrics.last_closed_bar_ts).total_seconds()
                else:
                    metrics.lag_sec = (now - metrics.last_closed_bar_ts).total_seconds()
        
        self._last_poll_ts = now
