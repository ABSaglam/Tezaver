from typing import Dict, Any
import uuid

class BinanceClientStub:
    """
    Stub implementation of BinanceClientPort.
    Determinisitc, offline, safe.
    """
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

    def ping(self) -> bool:
        return True

    def place_order(self, symbol: str, side: str, qty: float, price: float, reduce_only: bool, ts: int) -> Dict[str, Any]:
        return {
            "order_id": f"BORD_{symbol}_{ts}",
            "accepted": True,
            "dryrun": True, # Stub always dryruns effectively as it doesn't hit exchange
            "source": "STUB",
            "details": {
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": price,
                "reduce_only": reduce_only
            }
        }

    def get_account(self) -> Dict[str, Any]:
        return {
            "canTrade": True,
            "balances": [],
            "source": "STUB"
        }
