import time
import uuid
from typing import Dict, Any, Optional
from tezaver.matrix.adapters.binance_rest_client import BinanceRestClient

class RealBinanceBroker:
    """
    Broker adapter that talks to Real Binance API.
    Supports dry_run mode where it hits /order/test instead of /order.
    """
    def __init__(self, client: BinanceRestClient, dry_run: bool = True, reduce_only: bool = True):
        self.client = client
        self.dry_run = dry_run
        self.reduce_only = reduce_only # Default safety
        
    def place_order(self, strategy_id: str, symbol: str, action: str, qty: float, price: float, bar_ts: int) -> Dict[str, Any]:
        """
        Places a generic order.
        For Phase-14C.1, this is adapted to simple Action->Side logic.
        Action: BUY -> Long, SELL -> Short (or Close Long in simple mode)
        In Matrix v4 simple mode:
          BUY -> OPEN LONG
          SELL -> CLOSE LONG (ReduceOnly=True)
        """
        
        side = "BUY" if action == "BUY" else "SELL"
        
        # Prepare Params
        # newClientOrderId: using strategy_id + partial UUID to allow tracking
        # But for 14C.1 simple usage:
        cid = f"mx_{strategy_id}_{int(time.time())}_{str(uuid.uuid4())[:4]}"
        
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET", # Using MARKET for simplicity in this phase
            "quantity": qty,
            # "price": price, # Not for MARKET
            "newClientOrderId": cid
        }
        
        if self.reduce_only and side == "SELL":
            params["reduceOnly"] = "true"
            
        result = {}
        try:
            if self.dry_run:
                # Calls /order/test. Returns {} on success.
                self.client.order_test(params)
                result = {
                    "order_id": f"TEST_{cid}",
                    "accepted": True,
                    "dryrun": True,
                    "source": "BINANCE_REAL_TEST_ENDPOINT",
                    "params": params
                }
            else:
                # REAL!
                resp = self.client.order_place(params)
                result = {
                    "order_id": str(resp.get("orderId")),
                    "client_oid": resp.get("clientOrderId"),
                    "accepted": True,
                    "dryrun": False,
                    "source": "BINANCE_REAL",
                    "raw": resp
                }
        except Exception as e:
            result = {
                "accepted": False,
                "error": str(e),
                "source": "BINANCE_REAL_EXCEPTION",
                "params": params
            }
            
        return result
        
    def sync(self):
        return self.client.sync_time()
