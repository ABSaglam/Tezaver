from typing import Protocol, Optional
from tezaver.matrix.core.order_lifecycle import Order

class BrokerPort(Protocol):
    def place_order(self, order: Order) -> Order:
        """Places a new order. Returns the potentially updated order (e.g. with ID or status)."""
        ...

    def cancel_order(self, order_id: str) -> None:
        """Requests cancellation of an order."""
        ...
