"""
HOLD_NEXT_CLOSED Per-Cell Policy

Per-cell execution policy for effective-bar based hold/close.

State machine:
  IDLE → OPEN_SUBMITTED → EFFECTIVE_SET → CLOSE_SUBMITTED → IDLE

Invariants:
  - close_ts > effective_ts
  - reduceOnly=true for CLOSE
  - residual_after ≈ 0
  - Fingerprint dedup
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable
from enum import Enum
from datetime import datetime, timezone


class PolicyState(str, Enum):
    """Per-cell policy state."""
    IDLE = "IDLE"
    OPEN_SUBMITTED = "OPEN_SUBMITTED"
    EFFECTIVE_SET = "EFFECTIVE_SET"
    CLOSE_SUBMITTED = "CLOSE_SUBMITTED"


class PolicyName(str, Enum):
    """Available policies."""
    PASS_THROUGH = "PASS_THROUGH"
    HOLD_NEXT_CLOSED = "HOLD_NEXT_CLOSED"


@dataclass
class CellPolicyState:
    """Per-cell state for HOLD_NEXT_CLOSED policy."""
    state: PolicyState = PolicyState.IDLE
    # Timestamps
    open_trigger_bar_close_ts: Optional[str] = None
    open_effective_bar_close_ts: Optional[str] = None
    close_bar_close_ts: Optional[str] = None
    # Order info
    open_order_id: Optional[str] = None
    close_order_id: Optional[str] = None
    open_qty: float = 0.0
    close_qty: float = 0.0
    # Diagnostics
    seen_closed_count: int = 0
    bars_waited_effective: int = 0
    lag_sec_effective: float = 0.0
    residual_after: float = 0.0
    last_error: Optional[str] = None
    # Dust cleanup
    dust_policy: str = "IGNORE"
    dust_threshold: float = 0.002
    cleanup_attempted: bool = False
    cleanup_result: Optional[str] = None
    cleanup_order_id: Optional[str] = None
    # V5: min_hold_bars / pending_close
    pending_close: bool = False
    close_reason: Optional[str] = None  # SIGNAL_OK / SIGNAL_TOO_EARLY / PENDING_SIGNAL_RELEASED


@dataclass
class PolicyResult:
    """Result of policy tick."""
    action: str  # OPEN, CLOSE, WAIT, SKIP, DONE
    success: bool
    state: PolicyState
    order_id: Optional[str] = None
    error: Optional[str] = None
    bar_close_ts: Optional[str] = None


class HoldNextClosedPolicy:
    """
    HOLD_NEXT_CLOSED Policy.
    
    State machine:
      IDLE → (OPEN decision) → OPEN_SUBMITTED
      OPEN_SUBMITTED → (next bar) → EFFECTIVE_SET
      EFFECTIVE_SET → (next bar > effective) → CLOSE_SUBMITTED
      CLOSE_SUBMITTED → (success) → IDLE
    """
    
    EPS = 1e-12
    
    def __init__(
        self,
        gateway,
        event_sink: Optional[Callable] = None,
        qty: float = 0.002,
        min_pos_abs: float = 1e-12,
        exchange_mode: str = "REAL_TESTNET",
        armed: bool = True,
        exchange_enabled: bool = True,
        dust_policy: str = "IGNORE",
        dust_threshold: float = 0.002,
        close_qty_mult: float = 1.0,  # For BLOCK test - 0.5 = partial close
        close_policy: str = "NEXT_CLOSED_BAR",  # NEXT_CLOSED_BAR / NEXT_SIGNAL
        min_hold_bars: int = 1,  # Minimum bars to hold before CLOSE on NEXT_SIGNAL
        # Lifecycle config
        poll_order_sec: float = 2.0,
        order_timeout_sec: float = 30.0,
        cancel_on_timeout: bool = False,
        inject_fault: str = "NONE",
        inject_fault_nth: int = 0,  # 0=all orders, N=only fault Nth order
        inject_fault_action: str = "ANY",  # ANY/OPEN/CLOSE
        risk_limiter = None,  # Optional GlobalRiskLimiter for pre-trade checks
        auto_export_on_block: bool = False,  # Whether to export incident bundles on BLOCK
        mainnet_allowlist: str = None,  # Comma-separated allowlist for REAL_MAINNET
    ):
        # Wrap gateway with FaultInjectionGateway if needed
        if inject_fault and inject_fault != "NONE":
            from tezaver.matrix.live.live_gateway import FaultInjectionGateway
            self.gateway = FaultInjectionGateway(gateway, inject_fault, inject_fault_nth, inject_fault_action)
        else:
            self.gateway = gateway
        
        self._risk_limiter = risk_limiter
        self._auto_export_on_block = auto_export_on_block
        self._mainnet_allowlist_set = None
        if mainnet_allowlist:
            self._mainnet_allowlist_set = {s.strip().upper() for s in mainnet_allowlist.split(",") if s.strip()}
            
        self._event_sink = event_sink
        self.qty = qty
        self.min_pos_abs = min_pos_abs
        self.exchange_mode = exchange_mode
        self.armed = armed
        self.exchange_enabled = exchange_enabled
        self.dust_policy = dust_policy
        self.dust_threshold = dust_threshold
        self.close_qty_mult = close_qty_mult
        self.close_policy = close_policy
        self.min_hold_bars = min_hold_bars
        # Lifecycle params
        self.poll_order_sec = poll_order_sec
        self.order_timeout_sec = order_timeout_sec
        self.cancel_on_timeout = cancel_on_timeout
        
        # Per-cell state
        self.min_pos_abs = min_pos_abs
        self.exchange_mode = exchange_mode
        self.armed = armed
        self.exchange_enabled = exchange_enabled
        self.dust_policy = dust_policy
        self.dust_threshold = dust_threshold
        self.close_qty_mult = close_qty_mult
        self.close_policy = close_policy
        self.min_hold_bars = min_hold_bars
        
        # Per-cell state
        self._cells: Dict[str, CellPolicyState] = {}
        
        # Fingerprint dedup
        self._seen_fingerprints: set = set()
    
    def _cell_key(self, symbol: str, tf: str, profile_id: str) -> str:
        return f"{symbol}|{tf}|{profile_id}"
    
    def _fingerprint(self, symbol: str, tf: str, profile_id: str, bar_close_ts: str, action: str) -> str:
        return f"{symbol}|{tf}|{profile_id}|{bar_close_ts}|{action}"
    
    def get_cell_state(self, symbol: str, tf: str, profile_id: str) -> CellPolicyState:
        key = self._cell_key(symbol, tf, profile_id)
        if key not in self._cells:
            self._cells[key] = CellPolicyState()
        return self._cells[key]
    
    def reset_cell(self, symbol: str, tf: str, profile_id: str) -> None:
        """Reset cell state for a new cycle."""
        key = self._cell_key(symbol, tf, profile_id)
        self._cells[key] = CellPolicyState()
    
    def _emit_event(self, event: Dict[str, Any]) -> None:
        if self._event_sink:
            event.setdefault("exchange_mode", self.exchange_mode)
            event.setdefault("armed", self.armed)
            event.setdefault("exchange_enabled", self.exchange_enabled)
            if "ts" not in event:
                event["ts"] = datetime.now(timezone.utc).isoformat()
            self._event_sink(event)
    
    def _get_bar_sec(self, tf: str) -> int:
        """Get bar period in seconds."""
        if tf.endswith("m"):
            return int(tf[:-1]) * 60
        elif tf.endswith("h"):
            return int(tf[:-1]) * 3600
        return 60
    
    def handle_tick(
        self,
        symbol: str,
        tf: str,
        profile_id: str,
        bar_close_ts: str,
        decision: Optional[str] = None,  # "OPEN" or None
        strategy_signal: Optional[str] = None,  # "OPEN_LONG" / "CLOSE_LONG" / "NONE"
        cycle_idx: Optional[int] = None,
        htf_decision: Optional[str] = None,  # M3a: HTF Veto Context (e.g. "ALLOW", "VETO")
    ) -> PolicyResult:
        """
        Handle a closed bar tick for a cell.
        
        decision = "OPEN" means cluster says open a position.
        strategy_signal = "CLOSE_LONG" triggers CLOSE when close_policy=NEXT_SIGNAL.
        """
        from tezaver.matrix.live.live_gateway import ExchangeOrderRequest, OrderSide
        
        # M3a: HTF Permission Emission (Provider Logic)
        # If this is a HTF (4h or 1d), current signal determines permission for LTF
        if tf in ("4h", "1d"):
            # Determine permission based on current strategy signal
            # If strategy says OPEN -> ALLOW, else VETO
            # Note: This is a simplification. Real logic might check trend direction.
            # Assuming Long-only for now.
            permission = "ALLOW" if decision == "OPEN" else "VETO"
            
            # Emit Permission Event
            self._emit_event({
                "event_type": "HTF_PERMISSION_EVAL",
                "symbol": symbol,
                "timeframe": tf,
                "bar_close_ts": bar_close_ts,
                "decision": permission,
                "strategy_decision": decision,
            })
            # 4h usually acts as permission provider, might not trade itself in this setup?
            # Proceeding with standard logic just in case it trades too unless it's pure permission.
        
        cell = self.get_cell_state(symbol, tf, profile_id)
        
        # State machine
        if cell.state == PolicyState.IDLE:
            if decision == "OPEN":
                # M3a: Apply Veto Logic (Consumer Logic)
                # If LTF (15m) and we have HTF decision context
                if tf == "15m" and htf_decision:
                    if htf_decision == "VETO":
                        print(f"[POLICY] HTF_VETO_APPLIED {symbol}/{tf} htf={htf_decision}")
                        
                        self._emit_event({
                            "event_type": "HTF_VETO_APPLIED",
                            "symbol": symbol,
                            "timeframe": tf,
                            "bar_close_ts": bar_close_ts,
                            "htf_decision": htf_decision,
                        })
                        
                        # Block open
                        return PolicyResult(
                            action="VETOED", 
                            success=True, 
                            state=cell.state, 
                            bar_close_ts=bar_close_ts,
                            error="HTF Veto Applied"
                        )
                
                return self._handle_open(symbol, tf, profile_id, bar_close_ts, cell, cycle_idx=cycle_idx)
            else:
                return PolicyResult(action="SKIP", success=True, state=cell.state, bar_close_ts=bar_close_ts)
        
        elif cell.state == PolicyState.OPEN_SUBMITTED:
            # First bar after OPEN - set effective
            cell.seen_closed_count += 1
            cell.open_effective_bar_close_ts = bar_close_ts
            cell.state = PolicyState.EFFECTIVE_SET
            
            self._emit_event({
                "event_type": "ROUTER_POLICY_STATE",
                "policy": "HOLD_NEXT_CLOSED",
                "state": "EFFECTIVE_SET",
                "symbol": symbol,
                "timeframe": tf,
                "profile_id": profile_id,
                "open_trigger_bar_close_ts": cell.open_trigger_bar_close_ts,
                "open_effective_bar_close_ts": bar_close_ts,
            })
            
            print(f"[POLICY] EFFECTIVE_SET {symbol}/{tf} effective={bar_close_ts}")
            
            # V5: NEXT_SIGNAL + min_hold_bars - check if CLOSE_LONG arrived
            if self.close_policy == "NEXT_SIGNAL" and strategy_signal == "CLOSE_LONG":
                # Signal arrived on same bar as effective - too early
                if cell.bars_waited_effective < self.min_hold_bars:
                    cell.pending_close = True
                    cell.close_reason = "SIGNAL_TOO_EARLY"
                    print(f"[POLICY] SIGNAL_TOO_EARLY {symbol}/{tf} bars_waited={cell.bars_waited_effective} min_hold={self.min_hold_bars}")
                    return PolicyResult(action="SIGNAL_TOO_EARLY", success=True, state=cell.state, bar_close_ts=bar_close_ts)
                else:
                    # Signal OK - close now
                    cell.close_reason = "SIGNAL_OK"
                    cell.seen_closed_count += 1
                    return self._handle_close(symbol, tf, profile_id, bar_close_ts, cell, cycle_idx=cycle_idx)
            
            return PolicyResult(action="WAIT_EFFECTIVE", success=True, state=cell.state, bar_close_ts=bar_close_ts)
        
        elif cell.state == PolicyState.EFFECTIVE_SET:
            # Increment bars waited
            cell.bars_waited_effective += 1
            
            # NEXT_SIGNAL close policy
            if self.close_policy == "NEXT_SIGNAL":
                # Check if pending close should be released
                if cell.pending_close and cell.bars_waited_effective >= self.min_hold_bars:
                    cell.close_reason = "PENDING_SIGNAL_RELEASED"
                    print(f"[POLICY] PENDING_SIGNAL_RELEASED {symbol}/{tf} bars_waited={cell.bars_waited_effective}")
                    cell.seen_closed_count += 1
                    return self._handle_close(symbol, tf, profile_id, bar_close_ts, cell, cycle_idx=cycle_idx)
                
                # Check for new CLOSE_LONG signal
                if strategy_signal == "CLOSE_LONG":
                    if cell.bars_waited_effective >= self.min_hold_bars:
                        cell.close_reason = "SIGNAL_OK"
                        cell.seen_closed_count += 1
                        return self._handle_close(symbol, tf, profile_id, bar_close_ts, cell, cycle_idx=cycle_idx)
                    else:
                        cell.pending_close = True
                        cell.close_reason = "SIGNAL_TOO_EARLY"
                        print(f"[POLICY] SIGNAL_TOO_EARLY {symbol}/{tf} bars_waited={cell.bars_waited_effective}")
                        return PolicyResult(action="SIGNAL_TOO_EARLY", success=True, state=cell.state, bar_close_ts=bar_close_ts)
                
                # No signal - keep waiting
                return PolicyResult(action="WAIT_CLOSE_SIGNAL", success=True, state=cell.state, bar_close_ts=bar_close_ts)
            else:
                # Default: NEXT_CLOSED_BAR - trigger CLOSE on next bar
                if bar_close_ts <= cell.open_effective_bar_close_ts:
                    return PolicyResult(action="SKIP_OLD", success=True, state=cell.state, bar_close_ts=bar_close_ts)
                
                cell.seen_closed_count += 1
                return self._handle_close(symbol, tf, profile_id, bar_close_ts, cell, cycle_idx=cycle_idx)
        
        elif cell.state == PolicyState.CLOSE_SUBMITTED:
            # Already closed, reset to IDLE
            cell.state = PolicyState.IDLE
            return PolicyResult(action="RESET", success=True, state=cell.state, bar_close_ts=bar_close_ts)
        
        return PolicyResult(action="NO_OP", success=True, state=cell.state, bar_close_ts=bar_close_ts)
    
    def _handle_open(
        self,
        symbol: str,
        tf: str,
        profile_id: str,
        bar_close_ts: str,
        cell: CellPolicyState,
        cycle_idx: Optional[int] = None,
    ) -> PolicyResult:
        """Handle OPEN submission."""
        from tezaver.matrix.live.live_gateway import ExchangeOrderRequest, OrderSide
        
        fingerprint = self._fingerprint(symbol, tf, profile_id, bar_close_ts, "OPEN")
        
        # Dedup check
        if fingerprint in self._seen_fingerprints:
            return PolicyResult(action="DUPLICATE", success=False, state=cell.state, bar_close_ts=bar_close_ts)
        
        try:
            self._emit_event({
                "event_type": "ROUTER_POLICY_STATE",
                "policy": "HOLD_NEXT_CLOSED",
                "state": "OPEN_TRIGGER",
                "symbol": symbol,
                "timeframe": tf,
                "profile_id": profile_id,
                "bar_close_ts": bar_close_ts,
                "fingerprint": fingerprint,
                "cycle_idx": cycle_idx,
            })
            
            fp_short = fingerprint.replace("|", "_").replace(":", "-")[:36]
            
            req = ExchangeOrderRequest(
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=self.qty,
                reduce_only=False,
                client_id=fp_short,
            )
            

            
            # Use OrderLifecycleTracker
            from tezaver.matrix.live.order_lifecycle import OrderLifecycleTracker, OrderLifecycleResult
            
            # Order-time Allowlist Check (REAL_MAINNET safety net)
            if self._mainnet_allowlist_set and self.exchange_mode == "REAL_MAINNET":
                if symbol.upper() not in self._mainnet_allowlist_set:
                    reason = f"ALLOWLIST_VIOLATION_ORDER:{symbol}"
                    print(f"[POLICY] {reason}")
                    
                    # Emit telemetry and export incident
                    from tezaver.matrix.live.incident_bundle import maybe_export_on_block
                    maybe_export_on_block(
                        reason=reason,
                        enabled=self._auto_export_on_block,
                    )
                    
                    if self._event_sink:
                        from datetime import datetime, timezone
                        self._event_sink({
                            "event_type": "MAINNET_GUARD_EVAL",
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "decision": "BLOCK",
                            "reasons": [reason],
                            "symbol": symbol,
                            "allowlist": list(self._mainnet_allowlist_set),
                        })
                    
                    return PolicyResult(
                        action="ALLOWLIST_BLOCKED",
                        success=False,
                        state=cell.state,
                        bar_close_ts=bar_close_ts,
                    )
            
            # Risk Limiter Pre-Check (if configured)
            if self._risk_limiter:
                close_price = 42000.0  # Default price for DUMMY_ORDER mode
                risk_decision = self._risk_limiter.evaluate_new_order(
                    cell_id=fingerprint,
                    req_qty=self.qty,
                    price=close_price,
                    context={
                        "symbol": symbol,
                        "timeframe": tf,
                        "profile_id": profile_id,
                        "cycle_idx": cycle_idx,
                    }
                )
                
                if not risk_decision.allow:
                    # BLOCKED by risk limiter
                    print(f"[POLICY] RISK_LIMIT_BLOCK {symbol}/{tf}: {risk_decision.reason}")
                    
                    # Export incident bundle if enabled (uses global guard)
                    from tezaver.matrix.live.incident_bundle import maybe_export_on_block
                    maybe_export_on_block(
                        reason=f"RISK_LIMIT_BLOCK:{risk_decision.reason}",
                        enabled=self._auto_export_on_block,
                    )
                    
                    return PolicyResult(
                        action="RISK_BLOCKED",
                        success=False,
                        state=cell.state,
                        bar_close_ts=bar_close_ts,
                    )
            
            # 1. Submit
            submit_res = self.gateway.place_order(req)
            
            if submit_res.success:
                print(f"[POLICY] OPEN_SUBMIT_OK {symbol}/{tf} order_id={submit_res.order_id}")
                
                # 2. Track Lifecycle
                tracker = OrderLifecycleTracker(
                    gateway=self.gateway,
                    symbol=symbol,
                    order_id=submit_res.order_id,
                    client_order_id=fp_short,
                    poll_interval_sec=self.poll_order_sec,
                    max_wait_sec=self.order_timeout_sec,
                    cancel_on_timeout=self.cancel_on_timeout,

                    event_sink=self._event_sink,
                    context={
                        "action": "OPEN",
                        "symbol": symbol,
                        "timeframe": tf,
                        "profile_id": profile_id,
                        "fingerprint": fingerprint,
                        "cycle_idx": cycle_idx,
                    },
                    orig_qty=self.qty
                )
                
                lc_res = tracker.poll_until_terminal()
                
                if lc_res.is_success:
                    self._seen_fingerprints.add(fingerprint)
                    cell.state = PolicyState.OPEN_SUBMITTED
                    cell.open_trigger_bar_close_ts = bar_close_ts
                    cell.open_order_id = submit_res.order_id
                    cell.open_qty = lc_res.executed_qty  # Use actually executed qty
                    cell.seen_closed_count = 0
                    
                    print(f"[POLICY] OPEN_FILLED {symbol}/{tf} order_id={submit_res.order_id} executed_qty={lc_res.executed_qty}")
                    
                    self._emit_event({
                        "event_type": "ROUTER_POLICY_STATE",
                        "policy": "HOLD_NEXT_CLOSED",
                        "state": "OPEN_FILLED",
                        "symbol": symbol,
                        "timeframe": tf,
                        "profile_id": profile_id,
                        "bar_close_ts": bar_close_ts,
                        "order_id": submit_res.order_id,
                        "executed_qty": lc_res.executed_qty,
                        "avg_price": lc_res.avg_price,
                        "attempts": lc_res.attempts,
                        "fingerprint": fingerprint,
                    })
                    
                    return PolicyResult(
                        action="OPEN",
                        success=True,
                        state=cell.state,
                        order_id=submit_res.order_id,
                        bar_close_ts=bar_close_ts,
                    )
                else:
                    # Failed during lifecycle (e.g. TIMEOUT or REJECTED)
                    error_msg = f"OPEN failed: {lc_res.terminal_state} - {lc_res.error}"
                    cell.last_error = error_msg
                    
                    self._emit_event({
                        "event_type": "OPEN_FAIL_LIFECYCLE",
                        "symbol": symbol,
                        "timeframe": tf,
                        "profile_id": profile_id,
                        "order_id": submit_res.order_id,
                        "error": error_msg,
                        "terminal_state": lc_res.terminal_state.value,
                        "executed_qty": lc_res.executed_qty,
                        "cycle_idx": cycle_idx,
                    })

                    print(f"[POLICY] OPEN_FAIL_LIFECYCLE {symbol}/{tf}: {error_msg}")
                    return PolicyResult(action="OPEN", success=False, error=error_msg, state=cell.state, bar_close_ts=bar_close_ts)
            else:
                cell.last_error = submit_res.error
                return PolicyResult(action="OPEN", success=False, error=submit_res.error, state=cell.state, bar_close_ts=bar_close_ts)

        
        except Exception as e:
            cell.last_error = str(e)
            return PolicyResult(action="OPEN", success=False, error=str(e), state=cell.state, bar_close_ts=bar_close_ts)
    
    def _handle_close(
        self,
        symbol: str,
        tf: str,
        profile_id: str,
        bar_close_ts: str,
        cell: CellPolicyState,
        skip_monotonic_check: bool = False,  # For same-tick CLOSE in NEXT_SIGNAL mode
        cycle_idx: Optional[int] = None,
    ) -> PolicyResult:
        """Handle CLOSE submission with reduceOnly."""
        from tezaver.matrix.live.live_gateway import ExchangeOrderRequest, OrderSide
        
        fingerprint = self._fingerprint(symbol, tf, profile_id, bar_close_ts, "CLOSE")
        
        # Dedup check
        if fingerprint in self._seen_fingerprints:
            return PolicyResult(action="DUPLICATE", success=False, state=cell.state, bar_close_ts=bar_close_ts)
        
        try:
            # Tripwire: close_ts > effective_ts (skip if same-tick CLOSE allowed)
            if not skip_monotonic_check and bar_close_ts <= cell.open_effective_bar_close_ts:
                raise RuntimeError(f"Bar monotonicity: close_bar ({bar_close_ts}) <= effective_bar ({cell.open_effective_bar_close_ts})")
            
            
            self._emit_event({
                "event_type": "ROUTER_POLICY_STATE",
                "policy": "HOLD_NEXT_CLOSED",
                "state": "CLOSE_TRIGGER",
                "symbol": symbol,
                "timeframe": tf,
                "profile_id": profile_id,
                "bar_close_ts": bar_close_ts,
                "open_effective_bar_close_ts": cell.open_effective_bar_close_ts,
                "fingerprint": fingerprint,
            })
            
            # Get position
            pos_snapshot = self.gateway.get_position_snapshot(symbol)
            pos_amt_now = abs(float(pos_snapshot.get("position_qty", 0) or pos_snapshot.get("positionAmt", 0)))
            
            if pos_amt_now < self.EPS:
                print(f"[POLICY] CLOSE_SKIPPED {symbol}/{tf} no position")
                cell.state = PolicyState.IDLE
                return PolicyResult(action="CLOSE_SKIPPED", success=True, state=cell.state, bar_close_ts=bar_close_ts)
            
            close_qty = min(cell.open_qty, pos_amt_now)
            # Apply close_qty_mult for partial close testing (BLOCK proof)
            close_qty = close_qty * self.close_qty_mult
            cell.close_qty = close_qty
            
            fp_short = fingerprint.replace("|", "_").replace(":", "-")[:36]
            
            req = ExchangeOrderRequest(
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=close_qty,
                reduce_only=True,  # CRITICAL
                client_id=fp_short,
            )
            
            # Tripwire: reduceOnly must be true
            if not req.reduce_only:
                raise RuntimeError("CLOSE must have reduceOnly=true")
            
            if not req.reduce_only:
                raise RuntimeError("CLOSE must have reduceOnly=true")
                
            from tezaver.matrix.live.order_lifecycle import OrderLifecycleTracker, OrderLifecycleResult
            
            # 1. Submit
            submit_res = self.gateway.place_order(req)
            
            if submit_res.success:
                print(f"[POLICY] CLOSE_SUBMIT_OK {symbol}/{tf} order_id={submit_res.order_id}")
                
                # 2. Track Lifecycle
                tracker = OrderLifecycleTracker(
                    gateway=self.gateway,
                    symbol=symbol,
                    order_id=submit_res.order_id,
                    client_order_id=fp_short,
                    poll_interval_sec=self.poll_order_sec,
                    max_wait_sec=self.order_timeout_sec,
                    cancel_on_timeout=self.cancel_on_timeout,
                    event_sink=self._event_sink,
                    context={
                        "action": "CLOSE",
                        "symbol": symbol,
                        "timeframe": tf,
                        "profile_id": profile_id,
                        "fingerprint": fingerprint,
                        "cycle_idx": cycle_idx,
                    },
                    orig_qty=close_qty,
                )
                
                lc_res = tracker.poll_until_terminal()
                
                # Update cell state regardless of success (partial fills matter)
                self._seen_fingerprints.add(fingerprint)
                cell.state = PolicyState.CLOSE_SUBMITTED
                cell.close_bar_close_ts = bar_close_ts
                cell.close_order_id = submit_res.order_id
                
                if not lc_res.is_success:
                    # Failed during lifecycle - WARN or BLOCK
                    error_msg = f"CLOSE failed: {lc_res.terminal_state} - {lc_res.error}"
                    print(f"[POLICY] CLOSE_FAIL_LIFECYCLE {symbol}/{tf}: {error_msg}")
                    cell.last_error = error_msg
                    
                    # Emit failure event
                    self._emit_event({
                        "event_type": "CLOSE_FAIL_LIFECYCLE",
                        "symbol": symbol,
                        "timeframe": tf,
                        "profile_id": profile_id,
                        "order_id": submit_res.order_id,
                        "error": error_msg,
                        "terminal_state": lc_res.terminal_state.value,
                        "executed_qty": lc_res.executed_qty,
                        "cycle_idx": cycle_idx,
                    })
                    
                    # BLOCK if not filled at all? Or just return error.
                    # Per req: Handle CLOSE_FAIL_LIFECYCLE
                    return PolicyResult(action="CLOSE", success=False, error=error_msg, state=cell.state, bar_close_ts=bar_close_ts)
                
                # Success path
                print(f"[POLICY] CLOSE_FILLED {symbol}/{tf} order_id={submit_res.order_id} executed_qty={lc_res.executed_qty}")
                
                # Get residual
                pos_after = self.gateway.get_position_snapshot(symbol)
                cell.residual_after = abs(float(pos_after.get("position_qty", 0) or pos_after.get("positionAmt", 0)))
                
                # Store dust policy info in cell
                cell.dust_policy = self.dust_policy
                cell.dust_threshold = self.dust_threshold
                
                # ========== DUST POLICY HANDLING ==========
                residual_over_threshold = cell.residual_after > self.dust_threshold
                
                if residual_over_threshold:
                    if self.dust_policy == "BLOCK":
                        # Emit PROOF_BLOCKED event before failing
                        self._emit_event({
                            "event_type": "PROOF_BLOCKED",
                            "reason": "DUST_BLOCK",
                            "symbol": symbol,
                            "timeframe": tf,
                            "profile_id": profile_id,
                            "residual": cell.residual_after,
                            "threshold": self.dust_threshold,
                            "policy_params": {
                                "dust_policy": self.dust_policy,
                                "dust_threshold": self.dust_threshold,
                                "close_qty_mult": self.close_qty_mult,
                            },
                        })
                        # Fail immediately
                        raise RuntimeError(f"DUST_BLOCK: residual={cell.residual_after} > threshold={self.dust_threshold}")
                    
                    elif self.dust_policy == "FLATTEN_AFTER":
                        # Attempt cleanup order
                        cell.cleanup_attempted = True
                        try:
                            cleanup_qty = cell.residual_after
                            
                            # Round to step size if possible (simple round to 3 decimals)
                            cleanup_qty = round(cleanup_qty, 3)
                            
                            if cleanup_qty > 0:
                                cleanup_fp = f"{fingerprint}|CLEANUP"
                                cleanup_fp_short = cleanup_fp.replace("|", "_").replace(":", "-")[:36]
                                
                                cleanup_req = ExchangeOrderRequest(
                                    symbol=symbol,
                                    side=OrderSide.SELL,
                                    quantity=cleanup_qty,
                                    reduce_only=True,
                                    client_id=cleanup_fp_short,
                                )
                                
                                cleanup_result = self.gateway.place_order(cleanup_req)
                                
                                if cleanup_result.success:
                                    cell.cleanup_result = "SUCCESS"
                                    cell.cleanup_order_id = cleanup_result.order_id
                                    
                                    # Re-check residual
                                    pos_final = self.gateway.get_position_snapshot(symbol)
                                    cell.residual_after = abs(float(pos_final.get("position_qty", 0) or pos_final.get("positionAmt", 0)))
                                    
                                    print(f"[POLICY] CLEANUP_OK {symbol}/{tf} order_id={cleanup_result.order_id} residual_now={cell.residual_after}")
                                else:
                                    cell.cleanup_result = f"FAIL:{cleanup_result.error}"
                                    print(f"[POLICY] CLEANUP_FAIL {symbol}/{tf} error={cleanup_result.error}")
                            else:
                                cell.cleanup_result = "DUST_TOO_SMALL"
                        except Exception as ce:
                            cell.cleanup_result = f"ERROR:{str(ce)}"
                            print(f"[POLICY] CLEANUP_ERROR {symbol}/{tf}: {ce}")
                    
                    # IGNORE: do nothing, just accept the residual
                
                # Calculate effective metrics
                try:
                    bar_sec = self._get_bar_sec(tf)
                    effective_dt = datetime.fromisoformat(cell.open_effective_bar_close_ts.replace("Z", "+00:00"))
                    close_dt = datetime.fromisoformat(bar_close_ts.replace("Z", "+00:00"))
                    cell.lag_sec_effective = (close_dt - effective_dt).total_seconds()
                    cell.bars_waited_effective = round(cell.lag_sec_effective / bar_sec)
                except:
                    pass
                
                self._emit_event({
                    "event_type": "ROUTER_POLICY_STATE",
                    "policy": "HOLD_NEXT_CLOSED",
                    "state": "DONE",
                    "symbol": symbol,
                    "timeframe": tf,
                    "profile_id": profile_id,
                    "open_trigger_bar_close_ts": cell.open_trigger_bar_close_ts,
                    "open_effective_bar_close_ts": cell.open_effective_bar_close_ts,
                    "close_bar_close_ts": bar_close_ts,
                    "open_order_id": cell.open_order_id,
                    "close_order_id": cell.close_order_id,
                    "open_qty": cell.open_qty,
                    "close_qty": close_qty,
                    "residual_after": cell.residual_after,
                    "bars_waited_effective": cell.bars_waited_effective,
                    "lag_sec_effective": cell.lag_sec_effective,
                    "reduce_only": True,
                    # Dust fields
                    "dust_policy": self.dust_policy,
                    "dust_threshold": self.dust_threshold,
                    "cleanup_attempted": cell.cleanup_attempted,
                    "cleanup_result": cell.cleanup_result,
                    "cleanup_order_id": cell.cleanup_order_id,
                })
                
                cleanup_str = "YES" if cell.cleanup_attempted else "NO"
                print(f"[POLICY] CLOSE_OK {symbol}/{tf} order_id={submit_res.order_id} reduceOnly=true state={lc_res.terminal_state}")
                print(f"POLICY_DONE | {symbol}/{tf} open={cell.open_order_id} close={submit_res.order_id} eff_wait={cell.bars_waited_effective} eff_lag={cell.lag_sec_effective} residual={cell.residual_after} cleanup={cleanup_str}")
                
                # Reset to IDLE
                cell.state = PolicyState.IDLE
                
                return PolicyResult(
                    action="CLOSE",
                    success=True,
                    state=cell.state,
                    order_id=submit_res.order_id,
                    bar_close_ts=bar_close_ts,
                )
            else:
                cell.last_error = submit_res.error
                return PolicyResult(action="CLOSE", success=False, error=submit_res.error, state=cell.state, bar_close_ts=bar_close_ts)
        
        except RuntimeError as re:
            # Re-raise DUST_BLOCK to ensure exit_code != 0
            if "DUST_BLOCK" in str(re):
                print(f"[POLICY] BLOCKED: {re}")
                raise
            cell.last_error = str(re)
            return PolicyResult(action="CLOSE", success=False, error=str(re), state=cell.state, bar_close_ts=bar_close_ts)
        
        except Exception as e:
            cell.last_error = str(e)
            return PolicyResult(action="CLOSE", success=False, error=str(e), state=cell.state, bar_close_ts=bar_close_ts)
    
    def is_cycle_complete(self, symbol: str, tf: str, profile_id: str) -> bool:
        """Check if cell completed OPEN→CLOSE cycle."""
        cell = self.get_cell_state(symbol, tf, profile_id)
        return cell.close_order_id is not None and cell.state == PolicyState.IDLE
    
    def get_summary(self, symbol: str, tf: str, profile_id: str) -> Dict[str, Any]:
        """Get cell summary."""
        cell = self.get_cell_state(symbol, tf, profile_id)
        return {
            "state": cell.state.value,
            "open_order_id": cell.open_order_id,
            "close_order_id": cell.close_order_id,
            "open_effective_bar_close_ts": cell.open_effective_bar_close_ts,
            "close_bar_close_ts": cell.close_bar_close_ts,
            "bars_waited_effective": cell.bars_waited_effective,
            "lag_sec_effective": cell.lag_sec_effective,
            "residual_after": cell.residual_after,
            # Dust fields
            "dust_policy": cell.dust_policy,
            "dust_threshold": cell.dust_threshold,
            "cleanup_attempted": cell.cleanup_attempted,
            "cleanup_result": cell.cleanup_result,
            "cleanup_order_id": cell.cleanup_order_id,
        }
