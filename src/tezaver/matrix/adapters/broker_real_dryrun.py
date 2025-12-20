import uuid
from typing import Dict, Any

class RealDryRunBroker:
    """
    Simulation of a Real Broker Adapter in Dry Run mode.
    Does NOT send orders to exchange.
    Returns simulated acceptance and immediate fill for portfolio consistency in this phase.
    """
    def __init__(self, reduce_only: bool = True):
        self.reduce_only = reduce_only

    def place_order(self, strategy_id: str, symbol: str, side: str, qty: float, price: float, ts: int) -> Dict[str, Any]:
        """
        Simulates placing an order.
        In DryRun, we accept everything and log it.
        """
        # Generate ID that looks like real broker ID maybe?
        order_id = f"DRY_{uuid.uuid4().hex[:8]}"
        
        # Event Logic handled by caller (Cloud Runtime) usually, 
        # but adapter returns result.
        
        return {
            "order_id": order_id,
            "accepted": True,
            "dryrun": True,
            "details": {
                "symbol": symbol,
                "side": side,
                "qty": qty,
                "price": price,
                "reduce_only": self.reduce_only
            }
        }
