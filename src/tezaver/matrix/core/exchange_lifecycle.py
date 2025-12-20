import os
import json
import time
from typing import Dict, Any

class ExchangeOrderLifecycleTracker:
    """
    Tracks state of exchange orders to handle partial fills and idempotency.
    State is persisted in `exchange_orders.json`.
    """
    def __init__(self, home: str, strategy_id: str):
        self.home = home
        self.sid = strategy_id
        self.path = os.path.join(home, "cloud_runtime", "strategies", strategy_id, "exchange_orders.json")
        self.orders = self._load() # Map clientOrderId -> State
        
    def _load(self) -> Dict[str, Dict]:
        if os.path.exists(self.path):
            try:
                with open(self.path) as f: return json.load(f)
            except: pass
        return {}
        
    def _save(self):
        with open(self.path, "w") as f:
            json.dump(self.orders, f, indent=2)
            
    def update_order(self, event: Dict) -> float:
        """
        Updates order state from ORDER_TRADE_UPDATE execution report.
        Returns `delta_qty` (the amount of NEW filled quantity to apply).
        """
        # Event is the "o" dict from WS
        cid = event.get("c")
        cum_qty = float(event.get("z", 0))
        status = event.get("X")
        
        if cid not in self.orders:
            self.orders[cid] = {
                "clientOrderId": cid,
                "exchangeOrderId": str(event.get("i")),
                "status": status,
                "cumQty": 0.0,
                "createdTs": int(time.time()*1000)
            }
            
        order = self.orders[cid]
        prev_cum = order.get("cumQty", 0.0)
        
        delta = cum_qty - prev_cum
        
        # Update State
        order["status"] = status
        order["cumQty"] = cum_qty
        order["avgFillPrice"] = float(event.get("ap", 0) or event.get("L", 0)) 
        # Note: "ap" is Average Price, "L" is Last Price. "ap" is better for summary.
        order["lastUpdateTs"] = int(time.time()*1000)
        
        self.orders[cid] = order
        self._save()
        
        return max(0.0, delta)
