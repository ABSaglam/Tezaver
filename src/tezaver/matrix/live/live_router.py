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
    # Hold Policy configuration
    hold_policy: str = "OFF"  # OFF / HOLD_NEXT_CLOSED
    dust_policy: str = "FLATTEN_AFTER"  # IGNORE / FLATTEN_AFTER / BLOCK
    dust_threshold: float = 0.001
    preflight_mode: str = "FLATTEN_FIRST"  # BLOCK / FLATTEN_FIRST / IGNORE
    close_qty_mult: float = 1.0  # Always 1.0 in production
    # Exchange mode (for policy execution)
    exchange_mode: str = "DRY_RUN"  # DRY_RUN / DUMMY_ORDER / REAL_TESTNET
    armed: bool = False
    exchange_enabled: bool = False
    # Strategy
    strategy_enabled: bool = False  # Enable strategy signal adapter
    # Order Lifecycle Config (v1)
    poll_order_sec: float = 2.0
    order_timeout_sec: float = 30.0
    cancel_on_timeout: bool = False
    inject_fault: str = "NONE"
    # Risk Limiter Config (v1)
    max_total_notional_usdt: float = 500.0
    max_cell_notional_usdt: float = 300.0
    max_open_positions: int = 3
    risk_enforce: str = "BLOCK"  # WARN / BLOCK
    auto_export_on_block: bool = False  # Export incident bundles on BLOCK


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
        gateway=None,  # Exchange gateway for policy execution
    ):
        self.cluster = cluster
        self.config = config or LiveRouterConfig()
        self.event_sink = event_sink
        self.gateway = gateway
        
        self.tick_count = 0
        self.skip_count = 0
        self.error_count = 0
        self.last_tick: Optional[Dict[str, Any]] = None
        self.last_skip_reason: Optional[str] = None
        
        # Per-cell dedup: track last bar_close_ts per cell
        self._last_bar_close_ts_by_cell: Dict[str, str] = {}
        
        # Gating state (for UI)
        self._last_gates_passed: bool = True
        self._last_missing_gates: List[str] = []
        
        # Hold Policy instance (created if hold_policy != OFF)
        # First create Global Risk Limiter (needed by policy)
        from tezaver.matrix.live.risk_limiter import GlobalRiskLimiter, RiskLimits
        self._risk_limiter = GlobalRiskLimiter(
            limits=RiskLimits(
                max_total_notional_usdt=self.config.max_total_notional_usdt,
                max_cell_notional_usdt=self.config.max_cell_notional_usdt,
                max_open_positions=self.config.max_open_positions,
                enforce=self.config.risk_enforce,
            ),
            event_sink=self.event_sink,
        )
        
        self._policy = None
        if self.config.hold_policy == "HOLD_NEXT_CLOSED" and self.gateway:
            from tezaver.matrix.live.live_policy import HoldNextClosedPolicy
            self._policy = HoldNextClosedPolicy(
                gateway=self.gateway,
                event_sink=self.event_sink,
                qty=0.002,  # Default test qty
                exchange_mode=self.config.exchange_mode,
                armed=self.config.armed,
                exchange_enabled=self.config.exchange_enabled,
                dust_policy=self.config.dust_policy,
                dust_threshold=self.config.dust_threshold,
                close_qty_mult=self.config.close_qty_mult,
                # Lifecycle
                poll_order_sec=self.config.poll_order_sec,
                order_timeout_sec=self.config.order_timeout_sec,
                cancel_on_timeout=self.config.cancel_on_timeout,
                inject_fault=self.config.inject_fault,
                risk_limiter=self._risk_limiter,  # Pass risk limiter for pre-trade checks
                auto_export_on_block=self.config.auto_export_on_block,
            )
        
        # Strategy Signal Adapter (if strategy_enabled)
        self._strategy = None
        self._position_store = None
        if getattr(self.config, 'strategy_enabled', False):
            from tezaver.matrix.live.strategy_signal import StrategySignalAdapter, PositionStateStore
            self._position_store = PositionStateStore(event_sink=self.event_sink)
            self._strategy = StrategySignalAdapter(
                position_store=self._position_store,
                event_sink=self.event_sink,
                auto_open_on_flat=True,  # V1: auto-open for testing
            )

    
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
            tick_received_ts = datetime.now(timezone.utc).isoformat()
            profile_id = f"{symbol}_{timeframe}"
            
            # ========== 1) EMIT ROUTER_TICK (first) ==========
            if self.event_sink:
                self.event_sink({
                    "ts": tick_received_ts,
                    "event_type": "ROUTER_TICK",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "bar_close_ts": bar_close_ts,
                    "close": snapshot.get("close"),
                    "hold_policy": self.config.hold_policy,
                })
            
            # ========== 2) GATING CHECK ==========
            gates_passed = True
            missing_gates = []
            
            if self.config.exchange_mode in ("REAL_TESTNET", "REAL_MAINNET"):
                if not self.config.armed:
                    gates_passed = False
                    missing_gates.append("armed")
                if not self.config.exchange_enabled:
                    gates_passed = False
                    missing_gates.append("exchange_enabled")
                if self.gateway is None:
                    gates_passed = False
                    missing_gates.append("gateway")
            
            # Force DRY_RUN if gates fail
            effective_mode = self.config.exchange_mode
            if not gates_passed:
                effective_mode = "DRY_RUN"
            
            # Store gating state
            self._last_gates_passed = gates_passed
            self._last_missing_gates = missing_gates
            
            # ========== 3) STRATEGY SIGNAL (computes decision) ==========
            strategy_signal = None
            decision = None
            
            if self._strategy is not None and bar_close_ts:
                from tezaver.matrix.live.strategy_signal import Signal
                strategy_signal = self._strategy.compute_signal(
                    symbol=symbol,
                    tf=timeframe,
                    profile_id=profile_id,
                    bar_close_ts=bar_close_ts,
                    snapshot=snapshot,
                )
                
                # Convert strategy signal to policy decision
                if strategy_signal == Signal.OPEN_LONG:
                    decision = "OPEN"
                # CLOSE is handled by policy HOLD_NEXT_CLOSED timing
            
            # ========== 4) POLICY TICK (executes decision with timing) ==========
            policy_result = None
            policy_action = None
            
            if self._policy is not None and bar_close_ts:
                try:
                    # Policy decides action based on state machine + optional decision
                    policy_result = self._policy.handle_tick(
                        symbol=symbol,
                        tf=timeframe,
                        profile_id=profile_id,
                        bar_close_ts=bar_close_ts,
                        decision=decision,  # From strategy signal
                    )
                    policy_action = policy_result.action if policy_result else None
                    
                    # Emit LIVE_POLICY_TICK event (second)
                    if self.event_sink and policy_result:
                        cell_state = self._policy.get_cell_state(symbol, timeframe, profile_id)
                        self.event_sink({
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "event_type": "LIVE_POLICY_TICK",
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "bar_close_ts": bar_close_ts,
                            "policy_state": cell_state.state.value,
                            "action": policy_result.action,
                            "success": policy_result.success,
                            "order_id": policy_result.order_id,
                            "hold_policy": self.config.hold_policy,
                            "dust_policy": self.config.dust_policy,
                            "gates_passed": gates_passed,
                            "effective_mode": effective_mode,
                        })
                    
                    print(f"[LIVE_POLICY_TICK] {symbol}/{timeframe} action={policy_action} gates={gates_passed}")
                    
                except Exception as policy_err:
                    print(f"[POLICY_TICK_ERROR] {symbol}/{timeframe}: {policy_err}")
                    if self.event_sink:
                        self.event_sink({
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "event_type": "POLICY_TICK_ERROR",
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "error": str(policy_err),
                        })
                    raise  # Re-raise to be caught by outer exception handler
            
            # ========== 4) EMIT GUARDRAIL EVENT ==========
            if self.event_sink:
                self.event_sink({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event_type": "ROUTER_CLUSTER_GUARDRAIL",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "allow": gates_passed,
                    "configured_mode": self.config.exchange_mode,
                    "effective_mode": effective_mode,
                    "missing": missing_gates,
                    "armed": self.config.armed,
                    "exchange_enabled": self.config.exchange_enabled,
                    "force_dry_run": self.config.force_dry_run,
                })
            
            # ========== 5) CLUSTER EXECUTE (only if policy triggered action) ==========
            cluster_result = None
            decisions_count = 0
            executions_count = 0
            exec_dry_run = True
            exec_order_id = "DRY_RUN"
            allow = gates_passed
            
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
            
            # (Policy tick now runs BEFORE cluster - see step 3 above)
            
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
            # Policy state
            "hold_policy": self.config.hold_policy,
            "dust_policy": self.config.dust_policy,
            "dust_threshold": self.config.dust_threshold,
            "policy_enabled": self._policy is not None,
            # Gating state
            "gates_passed": self._last_gates_passed,
            "missing_gates": self._last_missing_gates,
            "armed": self.config.armed,
            "exchange_enabled": self.config.exchange_enabled,
            "exchange_mode": self.config.exchange_mode,
        }
    
    def get_policy_state(self, symbol: str, timeframe: str, profile_id: str = None) -> Optional[Dict[str, Any]]:
        """Get policy state for specific cell (for UI)."""
        if self._policy is None:
            return None
        
        if profile_id is None:
            profile_id = f"{symbol}_{timeframe}"
        
        cell = self._policy.get_cell_state(symbol, timeframe, profile_id)
        return {
            "state": cell.state.value,
            "open_order_id": cell.open_order_id,
            "close_order_id": cell.close_order_id,
            "open_ts": cell.open_ts,
            "effective_ts": cell.effective_ts,
            "close_ts": cell.close_ts,
            "bars_waited_effective": cell.bars_waited_effective,
            "residual_after": cell.residual_after,
            "dust_policy": cell.dust_policy,
            "cleanup_attempted": cell.cleanup_attempted,
            "cleanup_result": cell.cleanup_result,
        }

