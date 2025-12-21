from typing import Protocol, Optional
from tezaver.matrix.core.order_lifecycle import Order

class BrokerPort(Protocol):
    def place_order(self, order: Order) -> Order:
        """Places a new order. Returns the potentially updated order (e.g. with ID or status)."""
        ...

    def cancel_order(self, order_id: str) -> None:
        """Requests cancellation of an order."""
        ...

    def get_open_orders(self) -> list[dict]:
        """Returns a list of open orders from the exchange."""
        ...

    def get_positions(self) -> list[dict]:
        """Returns a list of current open positions from the exchange."""
        ...

    def get_server_time(self) -> int:
        """Returns exchange server time in milliseconds."""
        ...
