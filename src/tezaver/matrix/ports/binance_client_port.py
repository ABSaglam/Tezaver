from typing import Protocol, Dict, Any

class BinanceClientPort(Protocol):
    def ping(self) -> bool:
        ...

    def place_order(self, symbol: str, side: str, qty: float, price: float, reduce_only: bool, ts: int) -> Dict[str, Any]:
        """
        Returns order dict (order_id, etc.)
        """
        ...

    def get_account(self) -> Dict[str, Any]:
        ...
