# Matrix Live Order Lifecycle
"""
Order lifecycle tracking state machine.

Handles the transition from SUBMITTED -> CONFIRMED -> FILLED/TERMINAL.
Replaces "fire-and-forget" with active polling and verification.
"""

from __future__ import annotations

import time
import enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Protocol

# We need the gateway interface but avoid circular imports
class IGatewayLike(Protocol):
    def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]: ...
    def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]: ...


class OrderLifecycleState(str, enum.Enum):
    """Lifecycle states for an order."""
    UNKNOWN = "UNKNOWN"
    SUBMITTED = "SUBMITTED"           # Locally submitted, no confirmation yet
    NEW = "NEW"                       # Confirmed by exchange (open)
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # Partial execution
    FILLED = "FILLED"                 # Fully executed (Terminal)
    CANCELED = "CANCELED"             # Canceled by user/system (Terminal)
    REJECTED = "REJECTED"             # Rejected by exchange (Terminal)
    EXPIRED = "EXPIRED"               # Expired e.g. FOK/IOC (Terminal)
    TIMEOUT = "TIMEOUT"               # Polling timed out (Terminal-ish)


@dataclass
class OrderLifecycleResult:
    """Final result of the lifecycle tracking."""
    order_id: str
    client_order_id: str
    symbol: str
    terminal_state: OrderLifecycleState
    executed_qty: float
    orig_qty: float
    avg_price: float
    attempts: int
    poll_count: int
    duration_ms: float
    elapsed_sec: float
    is_success: bool  # True if FILLED or (PARTIALLY_FILLED and acceptable)
    error: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None


class OrderLifecycleTracker:
    """
    Tracks a single order until it reaches a terminal state or times out.
    """
    
    def __init__(
        self,
        gateway: IGatewayLike,
        symbol: str,
        order_id: str,
        client_order_id: str,
        poll_interval_sec: float = 2.0,
        max_wait_sec: float = 30.0,
        cancel_on_timeout: bool = False,
        event_sink: Optional[callable] = None,
        context: Optional[Dict[str, Any]] = None,
        orig_qty: float = 0.0,
    ):
        self._gateway = gateway
        self._symbol = symbol
        self._order_id = order_id
        self._client_id = client_order_id
        self._poll_interval = poll_interval_sec
        self._max_wait = max_wait_sec
        self._cancel_on_timeout = cancel_on_timeout
        self._event_sink = event_sink
        self._context = context or {}
        self._orig_qty = orig_qty
        
        self._state = OrderLifecycleState.SUBMITTED
        self._executed_qty = 0.0
        self._avg_price = 0.0
        self._attempts = 0
        self._start_time = 0.0
    
    def _emit(self, event_type: str, extra: Dict[str, Any] = None):
        """Emit telemetry event."""
        if not self._event_sink:
            return
            
        payload = {
            "event_type": event_type,
            "ts": self._now_iso(),
            "symbol": self._symbol,
            "order_id": self._order_id,
            "client_id": self._client_id,
            "state": self._state.value,
        }
        # Merge context first (so specific event fields override it if collision)
        if self._context:
            payload.update(self._context)
            
        if extra:
            payload.update(extra)
            
        self._event_sink(payload)

    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()

    def poll_until_terminal(self) -> OrderLifecycleResult:
        """
        Main blocking loop to poll order status.
        """
        self._start_time = time.time()
        
        self._emit("ORDER_LIFECYCLE_START", {
            "max_wait_sec": self._max_wait,
            "cancel_on_timeout": self._cancel_on_timeout,
            "orig_qty": self._orig_qty,
        })

        while True:
            self._attempts += 1
            elapsed = time.time() - self._start_time
            
            # 1. Fetch Status
            try:
                data = self._gateway.get_order(self._symbol, self._order_id)
                self._update_state(data)
                
                self._emit("ORDER_LIFECYCLE_POLL", {
                    "poll_count": self._attempts,
                    "elapsed_sec": elapsed,
                    "elapsed_ms": int(elapsed * 1000),
                    "last_status": data.get("status"),
                    "filled_qty": self._executed_qty,
                    "avg_price": self._avg_price,
                    "terminal_state": self._state.value if self._is_terminal(self._state) else None,
                    "reason": data.get("status"),
                })
                
            except Exception as e:
                self._emit("ORDER_POLL_ERROR", {"error": str(e), "attempt": self._attempts})
                # Don't break immediately on network error, retry until timeout
            
            # 2. Check Terminal
            if self._is_terminal(self._state):
                return self._finalize(success=self._state == OrderLifecycleState.FILLED)
            
            # 3. Check Timeout
            if elapsed >= self._max_wait:
                return self._handle_timeout(elapsed)
            
            # 4. Wait
            time.sleep(self._poll_interval)

    def _update_state(self, data: Dict[str, Any]):
        """Update internal state from gateway response."""
        status_str = data.get("status", "UNKNOWN")
        
        # Map exchange status to Enum
        # Binance: NEW, PARTIALLY_FILLED, FILLED, CANCELED, REJECTED, EXPIRED
        try:
            new_state = OrderLifecycleState(status_str)
        except ValueError:
            new_state = OrderLifecycleState.UNKNOWN
            
        qty = float(data.get("executedQty", 0.0))
        price = float(data.get("avgPrice", 0.0))
        
        # Detect Partial Fill Event
        if qty > self._executed_qty and self._executed_qty >= 0:
            delta = qty - self._executed_qty
            self._emit("ORDER_LIFECYCLE_PARTIAL", {
                "delta_qty": delta,
                "filled_qty": qty,
                "avg_price": price,
                "reason": "PARTIAL_FILL_DETECTED",
            })
        
        self._state = new_state
        self._executed_qty = qty
        self._avg_price = price

    def _is_terminal(self, state: OrderLifecycleState) -> bool:
        return state in (
            OrderLifecycleState.FILLED,
            OrderLifecycleState.CANCELED,
            OrderLifecycleState.REJECTED,
            OrderLifecycleState.EXPIRED
        )

    def _handle_timeout(self, elapsed: float) -> OrderLifecycleResult:
        self._state = OrderLifecycleState.TIMEOUT
        self._emit("ORDER_LIFECYCLE_TIMEOUT", {
            "elapsed_ms": int(elapsed * 1000),
            "elapsed_sec": elapsed,
            "filled_qty": self._executed_qty,
            "reason": "MAX_WAIT_EXCEEDED",
        })
        
        error_msg = f"Timed out after {elapsed:.1f}s"
        
        if self._cancel_on_timeout:
            self._emit("ORDER_CANCEL_ATTEMPT", {
                "reason": "TIMEOUT_GUARD",
                "elapsed_sec": elapsed,
                "filled_qty": self._executed_qty,
            })
            cancel_success = False
            cancel_error = None
            status = None
            try:
                cancel_res = self._gateway.cancel_order(self._symbol, self._order_id)
                status = cancel_res.get("status")
                if status == "CANCELED" or cancel_res.get("success") is True:
                    cancel_success = True
                    self._state = OrderLifecycleState.CANCELED
                    error_msg += " (Canceled)"
                else:
                    error_msg += f" (Cancel ack: {status})"
            except Exception as e:
                cancel_error = str(e)
                error_msg += f" (Cancel error: {str(e)})"
            
            self._emit("ORDER_CANCEL_RESULT", {
                "success": cancel_success,
                "cancel_status": status,
                "error": cancel_error,
                "filled_qty": self._executed_qty,
                "reason": "TIMEOUT_GUARD",
            })
            
            # One final state check after cancel attempt
            try:
                final_data = self._gateway.get_order(self._symbol, self._order_id)
                self._update_state(final_data)
            except:
                pass
            
            # Trust Cancel Ack if we are still NEW/PARTIAL after cancel
            if status == "CANCELED" and self._state not in (OrderLifecycleState.FILLED, OrderLifecycleState.CANCELED):
                self._state = OrderLifecycleState.CANCELED
            
            # If state updated to CANCELED/FILLED, update our return state
            if self._state == OrderLifecycleState.CANCELED:
                return self._finalize(success=False, error=error_msg + " [CANCELED]")
            elif self._state == OrderLifecycleState.FILLED:
                return self._finalize(success=True)

        return self._finalize(success=False, error=error_msg)

    def _finalize(self, success: bool, error: str = None) -> OrderLifecycleResult:
        duration = (time.time() - self._start_time) * 1000
        
        self._emit("ORDER_LIFECYCLE_DONE", {
            "final_state": self._state.value,
            "terminal_state": self._state.value,
            "executed_qty": self._executed_qty,
            "avg_price": self._avg_price,
            "orig_qty": self._orig_qty,
            "duration_ms": int(duration),
            "elapsed_sec": duration / 1000.0,
            "poll_count": self._attempts,
            "success": success,
        })
        
        return OrderLifecycleResult(
            order_id=self._order_id,
            client_order_id=self._client_id,
            symbol=self._symbol,
            terminal_state=self._state,
            executed_qty=self._executed_qty,
            orig_qty=self._orig_qty,
            avg_price=self._avg_price,
            attempts=self._attempts,
            poll_count=self._attempts,
            duration_ms=duration,
            elapsed_sec=duration / 1000.0,
            is_success=success,
            error=error,
        )
