from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional

class OrderStatus(Enum):
    NEW = auto()
    SUBMITTED = auto()
    ACKED = auto()
    PARTIALLY_FILLED = auto()
    FILLED = auto()
    CANCELED = auto()
    REJECTED = auto()
    TIMEOUT = auto()

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
    created_ts: float = 0.0
    updated_ts: float = 0.0

class OrderLifecycleTracker:
    def submit(self, order: Order) -> None:
        if order.status != OrderStatus.NEW:
            raise ValueError(f"Cannot submit order in status {order.status}")
        order.status = OrderStatus.SUBMITTED

    def ack(self, order: Order) -> None:
        if order.status != OrderStatus.SUBMITTED:
             # Depending on exchange, ack might come after fill? Assume standard flow for now.
             pass
        order.status = OrderStatus.ACKED

    def fill(self, order: Order, filled_qty: float, full_fill: bool) -> None:
        if full_fill:
            order.status = OrderStatus.FILLED
        else:
            order.status = OrderStatus.PARTIALLY_FILLED

    def reject(self, order: Order, reason: str) -> None:
        order.status = OrderStatus.REJECTED

    def timeout(self, order: Order) -> None:
        order.status = OrderStatus.TIMEOUT

    def cancel(self, order: Order) -> None:
        order.status = OrderStatus.CANCELED

def simulate_fault(order: Order, fault_type: str) -> None:
    """Helper for testing fault tolerance."""
    if fault_type == "TIMEOUT":
        order.status = OrderStatus.TIMEOUT
    elif fault_type == "REJECT":
        order.status = OrderStatus.REJECTED
    elif fault_type == "PARTIAL":
        order.status = OrderStatus.PARTIALLY_FILLED
