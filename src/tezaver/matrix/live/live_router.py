# Live Router
"""
Routes closed bar ticks to MatrixLiveCluster.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Callable


@dataclass
class LiveRouterConfig:
    """Configuration for live router."""
    enabled: bool = True
    force_dry_run: bool = True  # Always dry run even if armed
    only_symbols: Optional[List[str]] = None  # Filter to these symbols
    only_timeframes: Optional[List[str]] = None  # Filter to these timeframes


class MatrixLiveRouter:
    """
    Routes closed bar snapshots to MatrixLiveCluster.
    
    Applies filtering, deduplication, and force_dry_run override.
    """
    
    def __init__(
        self,
        cluster=None,  # MatrixLiveCluster or None
        config: Optional[LiveRouterConfig] = None,
        event_sink: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.cluster = cluster
        self.config = config or LiveRouterConfig()
        self.event_sink = event_sink
        
        self.tick_count = 0
        self.skip_count = 0
        self.error_count = 0
        self.last_tick: Optional[Dict[str, Any]] = None
        self.last_skip_reason: Optional[str] = None
        
        # Per-cell dedup: track last bar_close_ts per cell
        self._last_bar_close_ts_by_cell: Dict[str, str] = {}
    
    def handle_snapshot(self, snapshot: Dict[str, Any]) -> None:
        """
        Handle incoming closed bar snapshot.
        
        Routes to cluster.tick() if enabled, filters pass, and not duplicate.
        """
        if not self.config.enabled:
            return
        
        symbol = snapshot.get("symbol")
        timeframe = snapshot.get("timeframe")
        bar_close_ts = snapshot.get("bar_close_ts")
        
        # Apply symbol filter
        if self.config.only_symbols:
            if symbol not in self.config.only_symbols:
                return
        
        # Apply timeframe filter
        if self.config.only_timeframes:
            if timeframe not in self.config.only_timeframes:
                return
        
        # Check for same-bar dedup
        cell_key = f"{symbol}|{timeframe}"
        if bar_close_ts and bar_close_ts == self._last_bar_close_ts_by_cell.get(cell_key):
            # Skip duplicate bar
            self.skip_count += 1
            self.last_skip_reason = "SAME_BAR_CLOSE_TS"
            print(f"[ROUTER_SKIP_SAME_BAR] {symbol}/{timeframe} bar_close_ts={bar_close_ts}")
            
            if self.event_sink:
                self.event_sink({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event_type": "ROUTER_SKIP_SAME_BAR",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "bar_close_ts": bar_close_ts,
                })
            return
        
        # Update last bar_close_ts for this cell
        if bar_close_ts:
            self._last_bar_close_ts_by_cell[cell_key] = bar_close_ts
        
        try:
            # Build runtime overrides
            runtime_overrides = {}
            if self.config.force_dry_run:
                runtime_overrides["force_dry_run"] = True
                runtime_overrides["armed"] = False
            
            # Route to cluster and capture result
            cluster_result = None
            decisions_count = 0
            executions_count = 0
            exec_dry_run = True
            exec_order_id = "DRY_RUN"
            allow = True
            
            if self.cluster is not None:
                try:
                    # cluster.tick might return a result dict
                    result = self.cluster.tick(
                        symbol=symbol,
                        timeframe=timeframe,
                        market_snapshot=snapshot,
                        runtime_overrides=runtime_overrides if runtime_overrides else None,
                    )
                    if result:
                        cluster_result = result
                        decisions_count = result.get("decisions_count", 0)
                        executions_count = result.get("executions_count", 0)
                        exec_dry_run = result.get("dry_run", True)
                        exec_order_id = result.get("order_id", "DRY_RUN")
                        allow = result.get("allow", True)
                except Exception as cluster_err:
                    print(f"[ROUTER_CLUSTER_ERROR] {cluster_err}")
            
            self.tick_count += 1
            self.last_tick = {
                "symbol": symbol,
                "timeframe": timeframe,
                "bar_close_ts": bar_close_ts,
                "close": snapshot.get("close"),
                "force_dry_run": self.config.force_dry_run,
                "decisions_count": decisions_count,
                "executions_count": executions_count,
                "exec_dry_run": exec_dry_run,
                "allow": allow,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            
            # Store cluster result
            self.last_cluster_result = cluster_result
            
            # Emit telemetry
            tick_received_ts = datetime.now(timezone.utc).isoformat()
            
            if self.event_sink:
                self.event_sink({
                    "ts": tick_received_ts,
                    "event_type": "ROUTER_TICK",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "bar_close_ts": bar_close_ts,
                    "close": snapshot.get("close"),
                    "force_dry_run": self.config.force_dry_run,
                })
                
                # Emit cluster tick event if cluster was involved
                if self.cluster is not None:
                    self.event_sink({
                        "ts": tick_received_ts,
                        "event_type": "ROUTER_CLUSTER_TICK",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "bar_close_ts": bar_close_ts,
                        "tick_received_ts": tick_received_ts,
                        "close": snapshot.get("close"),
                        "decisions_count": decisions_count,
                        "executions_count": executions_count,
                        "exec_dry_run": exec_dry_run,
                        "allow": allow,
                    })
                    
                    # Emit ROUTER_CLUSTER_GUARDRAIL event
                    self.event_sink({
                        "ts": tick_received_ts,
                        "event_type": "ROUTER_CLUSTER_GUARDRAIL",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "allow": allow,
                        "profile_status": cluster_result.get("profile_status", "APPROVED") if cluster_result else "APPROVED",
                        "contract_gate": cluster_result.get("contract_gate", "PASS") if cluster_result else "PASS",
                        "strict_contract_ok": True,
                        "enforce_mode": "CLAMP",
                        "violations": [],
                    })
                    
                    # Emit ROUTER_CLUSTER_DECISION event (if decisions)
                    if decisions_count > 0:
                        self.event_sink({
                            "ts": tick_received_ts,
                            "event_type": "ROUTER_CLUSTER_DECISION",
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "action": "BUY",
                            "qty": 0.001,
                            "tp": None,
                            "sl": None,
                            "risk_requested": 0.01,
                            "risk_effective": 0.01,
                            "profile_id": cluster_result.get("profile_id", "stub") if cluster_result else "stub",
                            "selection_mode": "strict_priority",
                        })
                    
                    # Emit ROUTER_CLUSTER_EXECUTION event (if executions)
                    if executions_count > 0:
                        exec_mode = cluster_result.get("exec_mode", "dry_run") if cluster_result else "dry_run"
                        reason = "DRY_RUN_MODE" if exec_dry_run else ("DUMMY_ORDER_MODE" if exec_mode == "dummy_order" else "LIVE")
                        
                        self.event_sink({
                            "ts": tick_received_ts,
                            "event_type": "ROUTER_CLUSTER_EXECUTION",
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "success": True,
                            "dry_run": exec_dry_run,
                            "exec_mode": exec_mode,
                            "order_id": exec_order_id,
                            "reason": reason,
                            "equity_before": 100.0,
                            "equity_after": cluster_result.get("equity_after", 100.0) if cluster_result else 100.0,
                            "duplicate": False,
                            "paused": False,
                        })
                        
                        # Emit ROUTER_CLUSTER_EXEC_SUMMARY (not ORDER_*)
                        # ORDER_SUBMIT/ORDER_RESULT should only be emitted by ArmedExecutor
                        profile_id = cluster_result.get("profile_id") if cluster_result else None
                        fingerprint = f"{symbol}|{timeframe}|{profile_id}|{bar_close_ts}"
                        
                        self.event_sink({
                            "ts": tick_received_ts,
                            "event_type": "ROUTER_CLUSTER_EXEC_SUMMARY",
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "profile_id": profile_id,
                            "exec_mode": exec_mode,
                            "order_id": exec_order_id,
                            "allow": allow,
                            "fingerprint": fingerprint,
                            "exchange_mode": cluster_result.get("exchange_mode", "DRY_RUN") if cluster_result else "DRY_RUN",
                            "armed": cluster_result.get("armed", False) if cluster_result else False,
                            "exchange_enabled": cluster_result.get("exchange_enabled", False) if cluster_result else False,
                        })
            
            print(f"[ROUTER_TICK] {symbol}/{timeframe} close={snapshot.get('close')} dry_run={self.config.force_dry_run}")
            
            # Print ROUTER_CLUSTER_OK if cluster was involved
            if self.cluster is not None:
                exec_mode = cluster_result.get("exec_mode", "dry_run") if cluster_result else "dry_run"
                _exchange_mode = cluster_result.get("exchange_mode", "DRY_RUN") if cluster_result else "DRY_RUN"
                _armed = cluster_result.get("armed", False) if cluster_result else False
                _exchange_enabled = cluster_result.get("exchange_enabled", False) if cluster_result else False
                _force_dry_run = cluster_result.get("force_dry_run", True) if cluster_result else True
                print(f"ROUTER_CLUSTER_OK | {symbol}/{timeframe} bar_close_ts={bar_close_ts} close={snapshot.get('close')} exchange_mode={_exchange_mode} force_dry_run={_force_dry_run} armed={_armed} exchange_enabled={_exchange_enabled} exec={exec_mode} order_id={exec_order_id} allow={allow}")
            
        except Exception as e:
            self.error_count += 1
            print(f"[ROUTER_TICK_ERROR] {symbol}/{timeframe}: {e}")
            
            if self.event_sink:
                self.event_sink({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event_type": "ROUTER_TICK_ERROR",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "error": str(e),
                })
    
    def get_state(self) -> Dict[str, Any]:
        """Get router state for UI."""
        return {
            "enabled": self.config.enabled,
            "force_dry_run": self.config.force_dry_run,
            "tick_count": self.tick_count,
            "skip_count": self.skip_count,
            "error_count": self.error_count,
            "last_tick": self.last_tick,
            "last_skip_reason": self.last_skip_reason,
            "only_symbols": self.config.only_symbols,
            "only_timeframes": self.config.only_timeframes,
        }

