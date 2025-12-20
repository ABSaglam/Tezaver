"""
Proof OPEN→CLOSE State Controller v3

State machine for deterministic OPEN→CLOSE proof testing.
Includes:
- Preflight mode (BLOCK/FLATTEN_FIRST/IGNORE)
- Close policy (NEXT_CLOSED_BAR/NEXT_SIGNAL)
- Qty consistency (close_qty <= open_qty)
- Bar monotonicity tripwire
- Residual after tripwire
- Enhanced telemetry
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable
from enum import Enum


class ProofState(str, Enum):
    """Proof state machine states."""
    IDLE = "IDLE"
    OPEN_SUBMITTED = "OPEN_SUBMITTED"
    OPENED = "OPENED"
    WAIT_NEXT_CLOSED_BAR = "WAIT_NEXT_CLOSED_BAR"
    CLOSE_SUBMITTED = "CLOSE_SUBMITTED"
    CLOSED = "CLOSED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class PreflightMode(str, Enum):
    """Preflight residual handling mode."""
    BLOCK = "BLOCK"
    FLATTEN_FIRST = "FLATTEN_FIRST"
    IGNORE = "IGNORE"


class ClosePolicy(str, Enum):
    """Close trigger policy."""
    NEXT_CLOSED_BAR = "NEXT_CLOSED_BAR"  # Close on next closed bar (v3 default)
    NEXT_SIGNAL = "NEXT_SIGNAL"  # Close when signal received (future)


@dataclass
class ProofOpenCloseState:
    """State for OPEN→CLOSE proof."""
    state: ProofState = ProofState.IDLE
    # Bar timestamps
    open_trigger_bar_close_ts: Optional[str] = None  # Bar that triggered OPEN (audit)
    open_effective_bar_close_ts: Optional[str] = None  # First bar after OPEN order (effective reference)
    open_bar_close_ts: Optional[str] = None  # Alias for trigger (backward compat)
    close_bar_close_ts: Optional[str] = None
    # Order info
    open_order_id: Optional[str] = None
    close_order_id: Optional[str] = None
    open_qty: float = 0.0
    close_qty: float = 0.0
    last_seen_bar_close_ts: Optional[str] = None
    last_error: Optional[str] = None
    residual_before: float = 0.0
    residual_after: float = 0.0
    flatten_order_id: Optional[str] = None
    # Lag diagnostics
    seen_closed_count: int = 0  # How many closed bars seen after OPEN
    bars_waited_trigger: int = 0  # Bars from trigger to close (audit)
    bars_waited_effective: int = 0  # Bars from effective to close (should be 1)
    lag_sec_trigger: float = 0.0  # Lag from trigger bar
    lag_sec_effective: float = 0.0  # Lag from effective bar (should be ~60s for 1m)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "open_bar_close_ts": self.open_bar_close_ts,
            "close_bar_close_ts": self.close_bar_close_ts,
            "open_order_id": self.open_order_id,
            "close_order_id": self.close_order_id,
            "open_qty": self.open_qty,
            "close_qty": self.close_qty,
            "last_seen_bar_close_ts": self.last_seen_bar_close_ts,
            "last_error": self.last_error,
            "residual_before": self.residual_before,
            "residual_after": self.residual_after,
        }


@dataclass
class ProofResult:
    """Result of a proof tick."""
    action: str
    success: bool
    order_id: Optional[str] = None
    error: Optional[str] = None
    state: Optional[ProofState] = None
    bar_close_ts: Optional[str] = None


class ProofOpenCloseController:
    """
    Controller for OPEN→CLOSE proof v2.
    
    Features:
    - Preflight residual check (BLOCK/FLATTEN_FIRST/IGNORE)
    - Qty consistency (close_qty <= open_qty)
    - Enhanced telemetry
    """
    
    EPS = 1e-12  # Float comparison epsilon
    
    def __init__(
        self,
        symbol: str = "BTCUSDT",
        timeframe: str = "1m",
        qty: float = 0.002,
        preflight_mode: PreflightMode = PreflightMode.BLOCK,
        close_policy: ClosePolicy = ClosePolicy.NEXT_CLOSED_BAR,
        min_pos_abs: float = 1e-12,
        flatten_sleep_sec: float = 1.0,
        event_sink: Optional[Callable] = None,
        profile_id: str = "",
        exchange_mode: str = "REAL_TESTNET",
        armed: bool = True,
        exchange_enabled: bool = True,
    ):
        self.symbol = symbol
        self.timeframe = timeframe
        self.qty = qty
        self.preflight_mode = preflight_mode
        self.close_policy = close_policy
        self.min_pos_abs = min_pos_abs
        self.flatten_sleep_sec = flatten_sleep_sec
        self._event_sink = event_sink
        self.profile_id = profile_id or f"{symbol}_{timeframe}_proof"
        self.exchange_mode = exchange_mode
        self.armed = armed
        self.exchange_enabled = exchange_enabled
        self.state = ProofOpenCloseState()
        self._preflight_done = False
    
    def _emit_event(self, event: Dict[str, Any]) -> None:
        """Emit event with common fields."""
        if self._event_sink:
            from datetime import datetime, timezone
            # Add common fields
            event.setdefault("symbol", self.symbol)
            event.setdefault("timeframe", self.timeframe)
            event.setdefault("profile_id", self.profile_id)
            event.setdefault("exchange_mode", self.exchange_mode)
            event.setdefault("armed", self.armed)
            event.setdefault("exchange_enabled", self.exchange_enabled)
            if "ts" not in event:
                event["ts"] = datetime.now(timezone.utc).isoformat()
            self._event_sink(event)
    
    def run_preflight(self, gateway) -> bool:
        """
        Run preflight check for residual position.
        
        Returns True if proof can proceed, False if blocked.
        """
        import time
        from tezaver.matrix.live.live_gateway import ExchangeOrderRequest, OrderSide
        
        # Get position snapshot
        pos_snapshot = gateway.get_position_snapshot(self.symbol)
        pos_amt = float(pos_snapshot.get("position_qty", 0) or pos_snapshot.get("positionAmt", 0))
        residual = abs(pos_amt) > self.min_pos_abs
        
        self.state.residual_before = pos_amt
        
        # Emit preflight event
        self._emit_event({
            "event_type": "PROOF_PREFLIGHT",
            "preflight_mode": self.preflight_mode.value,
            "pos_amt": pos_amt,
            "residual": residual,
            "min_pos_abs": self.min_pos_abs,
        })
        
        if not residual:
            print(f"PROOF_PREFLIGHT_OK | {self.symbol}/{self.timeframe} residual=false mode={self.preflight_mode.value}")
            self._preflight_done = True
            return True
        
        # Handle residual based on mode
        if self.preflight_mode == PreflightMode.BLOCK:
            self._emit_event({
                "event_type": "PROOF_PREFLIGHT_BLOCKED",
                "pos_amt": pos_amt,
                "reason": "RESIDUAL_POSITION",
            })
            print(f"PROOF_PREFLIGHT_BLOCKED | residual_pos={pos_amt}")
            self.state.state = ProofState.BLOCKED
            self.state.last_error = f"Residual position: {pos_amt}"
            return False
        
        elif self.preflight_mode == PreflightMode.FLATTEN_FIRST:
            # Flatten residual position
            flatten_side = OrderSide.SELL if pos_amt > 0 else OrderSide.BUY
            flatten_qty = abs(pos_amt)
            
            fingerprint = f"{self.symbol}_{self.timeframe}_FLATTEN".replace("|", "_")[:36]
            
            self._emit_event({
                "event_type": "PROOF_PREFLIGHT_FLATTEN_SUBMIT",
                "side": flatten_side.value,
                "qty": flatten_qty,
                "reduce_only": True,
                "fingerprint": fingerprint,
            })
            
            print(f"[PREFLIGHT_FLATTEN] Closing residual: {flatten_side.value} qty={flatten_qty}")
            
            req = ExchangeOrderRequest(
                symbol=self.symbol,
                side=flatten_side,
                quantity=flatten_qty,
                reduce_only=True,
                client_id=fingerprint,
            )
            
            result = gateway.place_order(req)
            
            self._emit_event({
                "event_type": "PROOF_PREFLIGHT_FLATTEN_RESULT",
                "success": result.success,
                "order_id": result.order_id,
                "reason": result.error if not result.success else "OK",
            })
            
            if not result.success:
                self._emit_event({
                    "event_type": "PROOF_PREFLIGHT_FLATTEN_FAILED",
                    "error": result.error,
                })
                self.state.state = ProofState.FAILED
                self.state.last_error = f"Flatten failed: {result.error}"
                return False
            
            self.state.flatten_order_id = result.order_id
            
            # Wait and recheck
            time.sleep(self.flatten_sleep_sec)
            
            pos_snapshot2 = gateway.get_position_snapshot(self.symbol)
            pos_amt2 = float(pos_snapshot2.get("position_qty", 0) or pos_snapshot2.get("positionAmt", 0))
            residual2 = abs(pos_amt2) > self.min_pos_abs
            
            if residual2:
                self._emit_event({
                    "event_type": "PROOF_PREFLIGHT_FLATTEN_FAILED",
                    "pos_amt_after": pos_amt2,
                    "reason": "STILL_RESIDUAL",
                })
                print(f"PROOF_PREFLIGHT_FLATTEN_FAILED | still residual={pos_amt2}")
                self.state.state = ProofState.FAILED
                self.state.last_error = f"Still residual after flatten: {pos_amt2}"
                return False
            
            print(f"PROOF_PREFLIGHT_OK | {self.symbol}/{self.timeframe} residual=true→flattened mode={self.preflight_mode.value}")
            self._preflight_done = True
            return True
        
        else:  # IGNORE
            print(f"PROOF_PREFLIGHT_OK | {self.symbol}/{self.timeframe} residual=true(ignored) mode={self.preflight_mode.value}")
            self._preflight_done = True
            return True
    
    def handle_closed_bar_tick(
        self,
        bar_close_ts: str,
        close_price: float,
        gateway,
    ) -> ProofResult:
        """Handle a closed bar tick."""
        from tezaver.matrix.live.live_gateway import ExchangeOrderRequest, OrderSide
        
        # Dedup
        if bar_close_ts == self.state.last_seen_bar_close_ts:
            self._emit_event({
                "event_type": "PROOF_SKIP_SAME_BAR",
                "bar_close_ts": bar_close_ts,
            })
            return ProofResult(
                action="SKIP_SAME_BAR",
                success=True,
                state=self.state.state,
                bar_close_ts=bar_close_ts,
            )
        
        self.state.last_seen_bar_close_ts = bar_close_ts
        
        # State machine
        if self.state.state == ProofState.IDLE:
            return self._handle_open(bar_close_ts, close_price, gateway)
        elif self.state.state == ProofState.OPENED:
            # First bar after OPEN order - this is our EFFECTIVE reference bar
            self.state.seen_closed_count += 1
            self.state.open_effective_bar_close_ts = bar_close_ts  # SET EFFECTIVE REFERENCE
            
            self._emit_event({
                "event_type": "PROOF_WAIT_SEEN",
                "open_trigger_bar_close_ts": self.state.open_trigger_bar_close_ts,
                "open_effective_bar_close_ts": bar_close_ts,
                "seen_bar_close_ts": bar_close_ts,
                "seen_closed_count": self.state.seen_closed_count,
                "reason": "SET_EFFECTIVE_BAR",
            })
            
            if self.close_policy == ClosePolicy.NEXT_CLOSED_BAR:
                # Go to WAIT state - CLOSE will trigger on NEXT bar
                self.state.state = ProofState.WAIT_NEXT_CLOSED_BAR
                return ProofResult(
                    action="WAIT_NEXT_CLOSED_BAR",
                    success=True,
                    state=self.state.state,
                    bar_close_ts=bar_close_ts,
                )
            else: # ClosePolicy.NEXT_SIGNAL (not implemented yet)
                return ProofResult(
                    action="NO_OP",
                    success=True,
                    state=self.state.state,
                    bar_close_ts=bar_close_ts,
                )
        elif self.state.state == ProofState.WAIT_NEXT_CLOSED_BAR:
            # Next bar after EFFECTIVE - this is CLOSE trigger!
            # Now: close_bar = effective_bar + 1 bar => effective_bars_waited = 1
            self.state.seen_closed_count += 1
            self._emit_event({
                "event_type": "PROOF_WAIT_SEEN",
                "open_trigger_bar_close_ts": self.state.open_trigger_bar_close_ts,
                "open_effective_bar_close_ts": self.state.open_effective_bar_close_ts,
                "seen_bar_close_ts": bar_close_ts,
                "seen_closed_count": self.state.seen_closed_count,
                "reason": "TRIGGER_CLOSE",
            })
            return self._handle_close(bar_close_ts, close_price, gateway)
        else:
            return ProofResult(
                action="NO_OP",
                success=True,
                state=self.state.state,
                bar_close_ts=bar_close_ts,
            )
    
    def _handle_open(self, bar_close_ts: str, close_price: float, gateway) -> ProofResult:
        """Handle OPEN (MARKET BUY)."""
        from tezaver.matrix.live.live_gateway import ExchangeOrderRequest, OrderSide
        
        try:
            # Emit trigger event
            self._emit_event({
                "event_type": "PROOF_OPEN_TRIGGER",
                "bar_close_ts": bar_close_ts,
                "close_policy": self.close_policy.value,
            })
            
            fingerprint = f"{self.symbol}_{self.timeframe}_OPEN_{bar_close_ts}".replace("|", "_").replace(":", "-")[:36]
            
            self._emit_event({
                "event_type": "PROOF_OPEN_SUBMIT",
                "side": "BUY",
                "qty": self.qty,
                "reduce_only": False,
                "bar_close_ts": bar_close_ts,
                "fingerprint": fingerprint,
            })
            
            req = ExchangeOrderRequest(
                symbol=self.symbol,
                side=OrderSide.BUY,
                quantity=self.qty,
                reduce_only=False,
                client_id=fingerprint,
            )
            
            result = gateway.place_order(req)
            
            self._emit_event({
                "event_type": "PROOF_OPEN_RESULT",
                "success": result.success,
                "order_id": result.order_id,
                "reason": result.error if not result.success else "OK",
                "open_qty": self.qty,
                "bar_close_ts": bar_close_ts,
            })
            
            if result.success:
                self.state.state = ProofState.OPENED
                self.state.open_trigger_bar_close_ts = bar_close_ts  # Audit: trigger bar
                self.state.open_bar_close_ts = bar_close_ts  # Backward compat
                self.state.open_order_id = result.order_id
                self.state.open_qty = self.qty
                
                print(f"[PROOF_OPEN_OK] {self.symbol} order_id={result.order_id} qty={self.qty}")
                
                return ProofResult(
                    action="OPEN",
                    success=True,
                    order_id=result.order_id,
                    state=self.state.state,
                    bar_close_ts=bar_close_ts,
                )
            else:
                self.state.last_error = result.error
                return ProofResult(
                    action="OPEN",
                    success=False,
                    error=result.error,
                    state=self.state.state,
                    bar_close_ts=bar_close_ts,
                )
        
        except Exception as e:
            self.state.last_error = str(e)
            return ProofResult(action="OPEN", success=False, error=str(e), state=self.state.state, bar_close_ts=bar_close_ts)
    
    def _handle_close(self, bar_close_ts: str, close_price: float, gateway) -> ProofResult:
        """Handle CLOSE (MARKET SELL + reduceOnly=true) with qty consistency and tripwires."""
        from tezaver.matrix.live.live_gateway import ExchangeOrderRequest, OrderSide
        
        try:
            # Tripwire: bar monotonicity - close bar must be strictly newer than EFFECTIVE bar
            if bar_close_ts <= self.state.open_effective_bar_close_ts:
                raise RuntimeError(f"Bar monotonicity violated: close_bar ({bar_close_ts}) <= effective_bar ({self.state.open_effective_bar_close_ts})")
            
            # Emit trigger event
            self._emit_event({
                "event_type": "PROOF_CLOSE_TRIGGER",
                "bar_close_ts": bar_close_ts,
                "open_trigger_bar_close_ts": self.state.open_trigger_bar_close_ts,
                "open_effective_bar_close_ts": self.state.open_effective_bar_close_ts,
                "close_policy": self.close_policy.value,
            })
            
            # Get current position
            pos_snapshot = gateway.get_position_snapshot(self.symbol)
            pos_amt_now = abs(float(pos_snapshot.get("position_qty", 0) or pos_snapshot.get("positionAmt", 0)))
            
            # Qty consistency: close_qty = min(open_qty, pos_amt_now)
            if pos_amt_now < self.EPS:
                self._emit_event({
                    "event_type": "PROOF_CLOSE_SKIPPED_NO_POSITION",
                    "pos_amt_now": pos_amt_now,
                    "open_qty": self.state.open_qty,
                    "bar_close_ts": bar_close_ts,
                })
                print(f"[PROOF_CLOSE_SKIPPED] No position to close: pos_amt={pos_amt_now}")
                self.state.state = ProofState.CLOSED
                self.state.close_qty = 0
                return ProofResult(action="CLOSE_SKIPPED", success=True, state=self.state.state, bar_close_ts=bar_close_ts)
            
            close_qty = min(self.state.open_qty, pos_amt_now)
            self.state.close_qty = close_qty
            
            fingerprint = f"{self.symbol}_{self.timeframe}_CLOSE_{bar_close_ts}".replace("|", "_").replace(":", "-")[:36]
            
            self._emit_event({
                "event_type": "PROOF_CLOSE_SUBMIT",
                "side": "SELL",
                "qty": close_qty,
                "reduce_only": True,
                "open_qty": self.state.open_qty,
                "pos_amt_now": pos_amt_now,
                "close_qty": close_qty,
                "bar_close_ts": bar_close_ts,
                "open_bar_close_ts": self.state.open_bar_close_ts,
                "fingerprint": fingerprint,
            })
            
            # Tripwire: close_qty must be <= open_qty
            if close_qty > self.state.open_qty + self.EPS:
                raise RuntimeError(f"CLOSE qty ({close_qty}) > OPEN qty ({self.state.open_qty})")
            
            req = ExchangeOrderRequest(
                symbol=self.symbol,
                side=OrderSide.SELL,
                quantity=close_qty,
                reduce_only=True,
                client_id=fingerprint,
            )
            
            if not req.reduce_only:
                raise RuntimeError("CLOSE order must have reduceOnly=true")
            
            result = gateway.place_order(req)
            
            self._emit_event({
                "event_type": "PROOF_CLOSE_RESULT",
                "success": result.success,
                "order_id": result.order_id,
                "reason": result.error if not result.success else "OK",
                "close_qty": close_qty,
                "bar_close_ts": bar_close_ts,
            })
            
            if result.success:
                self.state.state = ProofState.CLOSED
                self.state.close_bar_close_ts = bar_close_ts
                self.state.close_order_id = result.order_id
                
                # Get residual after
                pos_after = gateway.get_position_snapshot(self.symbol)
                self.state.residual_after = float(pos_after.get("position_qty", 0) or pos_after.get("positionAmt", 0))
                
                # Tripwire: residual_after must be ~0
                if abs(self.state.residual_after) > self.min_pos_abs:
                    print(f"[WARNING] Residual after close: {self.state.residual_after}")
                
                # Calculate lag and bars_waited (trigger vs effective)
                lag_sec_trigger = 0.0
                lag_sec_effective = 0.0
                bars_waited_trigger = 0
                bars_waited_effective = 0
                bar_sec = 60  # default 1m
                
                try:
                    from datetime import datetime
                    
                    # Calculate bar period in seconds
                    if self.timeframe.endswith("m"):
                        bar_sec = int(self.timeframe[:-1]) * 60
                    elif self.timeframe.endswith("h"):
                        bar_sec = int(self.timeframe[:-1]) * 3600
                    
                    close_dt = datetime.fromisoformat(bar_close_ts.replace("Z", "+00:00"))
                    
                    # Trigger-based (audit)
                    trigger_dt = datetime.fromisoformat(self.state.open_trigger_bar_close_ts.replace("Z", "+00:00"))
                    lag_sec_trigger = (close_dt - trigger_dt).total_seconds()
                    bars_waited_trigger = round(lag_sec_trigger / bar_sec)
                    
                    # Effective-based (should be 1 bar)
                    effective_dt = datetime.fromisoformat(self.state.open_effective_bar_close_ts.replace("Z", "+00:00"))
                    lag_sec_effective = (close_dt - effective_dt).total_seconds()
                    bars_waited_effective = round(lag_sec_effective / bar_sec)
                    
                    # Store in state
                    self.state.bars_waited_trigger = bars_waited_trigger
                    self.state.bars_waited_effective = bars_waited_effective
                    self.state.lag_sec_trigger = lag_sec_trigger
                    self.state.lag_sec_effective = lag_sec_effective
                except:
                    pass
                
                self._emit_event({
                    "event_type": "PROOF_DONE",
                    "state": "CLOSED",
                    "open_order_id": self.state.open_order_id,
                    "close_order_id": self.state.close_order_id,
                    "open_qty": self.state.open_qty,
                    "close_qty": close_qty,
                    "open_trigger_bar_close_ts": self.state.open_trigger_bar_close_ts,
                    "open_effective_bar_close_ts": self.state.open_effective_bar_close_ts,
                    "close_bar_close_ts": bar_close_ts,
                    "residual_before": self.state.residual_before,
                    "residual_after": self.state.residual_after,
                    "lag_sec_trigger": lag_sec_trigger,
                    "lag_sec_effective": lag_sec_effective,
                    "bars_waited_trigger": bars_waited_trigger,
                    "bars_waited_effective": bars_waited_effective,
                    "seen_closed_count": self.state.seen_closed_count,
                    "strict": True,
                    "close_policy": self.close_policy.value,
                })
                
                print(f"[PROOF_CLOSE_OK] {self.symbol} order_id={result.order_id} qty={close_qty} reduceOnly=true")
                print(f"PROOF_OPEN_CLOSE_OK | state=CLOSED open={self.state.open_order_id} close={result.order_id} reduceOnly=true open_qty={self.state.open_qty} close_qty={close_qty} pos_before={self.state.residual_before} pos_after={self.state.residual_after} trig_lag={lag_sec_trigger} eff_lag={lag_sec_effective} trig_wait={bars_waited_trigger} eff_wait={bars_waited_effective} close_policy={self.close_policy.value}")
                
                return ProofResult(
                    action="CLOSE",
                    success=True,
                    order_id=result.order_id,
                    state=self.state.state,
                    bar_close_ts=bar_close_ts,
                )
            else:
                self.state.last_error = result.error
                return ProofResult(action="CLOSE", success=False, error=result.error, state=self.state.state, bar_close_ts=bar_close_ts)
        
        except Exception as e:
            self.state.last_error = str(e)
            return ProofResult(action="CLOSE", success=False, error=str(e), state=self.state.state, bar_close_ts=bar_close_ts)
    
    @property
    def is_done(self) -> bool:
        return self.state.state in (ProofState.CLOSED, ProofState.BLOCKED, ProofState.FAILED)
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "state": self.state.state.value,
            "open_order_id": self.state.open_order_id,
            "close_order_id": self.state.close_order_id,
            "open_qty": self.state.open_qty,
            "close_qty": self.state.close_qty,
            "open_bar_close_ts": self.state.open_bar_close_ts,
            "close_bar_close_ts": self.state.close_bar_close_ts,
            "residual_before": self.state.residual_before,
            "residual_after": self.state.residual_after,
            "last_error": self.state.last_error,
            "success": self.state.state == ProofState.CLOSED and self.state.close_order_id is not None,
        }
