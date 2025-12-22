from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import time

class OrderStatus(Enum):
    NEW = auto()
    SUBMITTED = auto()
    ACKED = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCELED = auto()
    REJECTED = auto()
    TIMEOUT = auto()
    CANCEL_REQUESTED = auto()

@dataclass
class Order:
    order_id: str
    symbol: str
    side: str
    qty: float
    limit_price: float = 0.0
    status: OrderStatus = OrderStatus.NEW
    
    # Fill metrics (MXI-1120)
    fill_price: float = 0.0
    fill_qty: float = 0.0
    fee_cost: float = 0.0
    slippage_cost: float = 0.0
    
    # Time info
    created_ts: float = field(default_factory=time.time)
    updated_ts: float = field(default_factory=time.time)
    
    # MX-5200: Lifecycle History
    history: List[Dict[str, Any]] = field(default_factory=list)
    client_order_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    
    def is_terminal(self) -> bool:
        return self.status in (OrderStatus.FILLED, OrderStatus.CANCELED, OrderStatus.REJECTED, OrderStatus.TIMEOUT)

class OrderLifecycleTracker:
    def __init__(self, run_id: str, emit_fn=None):
        self.run_id = run_id
        self.emit_fn = emit_fn

    def _update_state(self, order: Order, new_status: OrderStatus, reason: str = "", extra: Dict = None):
        # MX-9370: Raise ValueError on invalid transition from terminal state
        if order.is_terminal():
            raise ValueError(f"INVALID_TRANSITION:{order.status.name}->{new_status.name}")

        old_status = order.status
        order.status = new_status
        order.updated_ts = time.time()
        
        entry = {
            "ts": order.updated_ts,
            "old_status": old_status.name,
            "new_status": new_status.name,
            "reason": reason,
            **(extra or {})
        }
        order.history.append(entry)

        if self.emit_fn:
            self.emit_fn("ORDER_STATE_TRANSITION", {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "old_status": old_status.name,
                "new_status": new_status.name,
                "reason": reason
            })

    def submit(self, order: Order) -> None:
        self._update_state(order, OrderStatus.SUBMITTED)

    def ack(self, order: Order, exchange_id: str = None) -> None:
        if exchange_id:
            order.exchange_order_id = exchange_id
        self._update_state(order, OrderStatus.ACKED)

    def partial_fill(self, order: Order, fill_qty_delta: float, fill_price: float) -> None:
        # Update cumulative fill metrics
        total_qty = order.fill_qty + fill_qty_delta
        # Weighted average price
        if total_qty > 0:
            order.fill_price = ((order.fill_price * order.fill_qty) + (fill_price * fill_qty_delta)) / total_qty
        order.fill_qty = total_qty
        
        self._update_state(order, OrderStatus.PARTIALLY_FILLED, extra={"delta": fill_qty_delta, "price": fill_price})
        
        if self.emit_fn:
            self.emit_fn("PARTIAL_FILL_HANDLED", {
                "order_id": order.order_id,
                "symbol": order.symbol,
                "delta": fill_qty_delta,
                "remaining": order.qty - order.fill_qty
            })

    def fill(self, order: Order, fill_price: float = None) -> None:
        if fill_price:
            # Final fill price update
            if order.fill_qty == 0:
                order.fill_price = fill_price
                order.fill_qty = order.qty
            else:
                # If we had partials, the last fill price might be slightly different or same
                # For v1, assume last price applies to remainder
                remainder = order.qty - order.fill_qty
                if remainder > 0:
                    order.fill_price = ((order.fill_price * order.fill_qty) + (fill_price * remainder)) / order.qty
                    order.fill_qty = order.qty
        else:
            # If no price provided, assume full qty filled at limit or existing avg
            order.fill_qty = order.qty
            
        self._update_state(order, OrderStatus.FILLED)

    def reject(self, order: Order, reason: str) -> None:
        self._update_state(order, OrderStatus.REJECTED, reason=reason)
        if self.emit_fn:
            self.emit_fn("ORDER_REJECTED", {"order_id": order.order_id, "reason": reason})

    def timeout(self, order: Order) -> None:
        self._update_state(order, OrderStatus.TIMEOUT)
        if self.emit_fn:
            self.emit_fn("ORDER_TIMEOUT", {"order_id": order.order_id})

    def cancel_requested(self, order: Order) -> None:
        self._update_state(order, OrderStatus.CANCEL_REQUESTED)

    def canceled(self, order: Order, reason: str = "") -> None:
        self._update_state(order, OrderStatus.CANCELED, reason=reason)
        if self.emit_fn:
            if "TIMEOUT" in reason:
                self.emit_fn("CANCEL_ON_TIMEOUT", {"order_id": order.order_id})

def simulate_fault(order: Order, fault_type: str) -> None:
    """Helper for testing fault tolerance."""
    if fault_type == "TIMEOUT":
        order.status = OrderStatus.TIMEOUT
    elif fault_type == "REJECT":
        order.status = OrderStatus.REJECTED
    elif fault_type == "PARTIAL":
        order.status = OrderStatus.PARTIALLY_FILLED
