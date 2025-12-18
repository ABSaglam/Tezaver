# Tezaver Bulut - Fill Sync Service
"""
Syncs 'User Trades' (Fills) from Binance and calculates exact PnL/Fee.
"""

import time
from typing import Optional, List, Dict
from dataclasses import dataclass

from tezaver.bulut.core.config import BulutConfig

@dataclass
class FillSummary:
    symbol: str
    order_id: int
    qty: float
    vwap: float
    realized_pnl: float
    commission: float
    net_pnl: float
    ts_first: int
    ts_last: int


class FillSyncService:
    """
    Syncs execution fills to audit PnL accurately.
    """
    def __init__(self, config: BulutConfig, binance_client, telemetry, persistence, time_sync):
        self._config = config
        self._client = binance_client
        self._telemetry = telemetry
        self._persistence = persistence
        self._time_sync = time_sync
        
    async def sync_order_fills(
        self, 
        symbol: str, 
        order_id: Optional[int] = None, 
        client_order_id: Optional[str] = None, 
        window_ms: int = 600000 # 10 minutes default lookback
    ) -> Optional[FillSummary]:
        """
        Fetch user trades and aggregate for specific order.
        Returns FillSummary if found, None otherwise.
        """
        # Time Window
        now_ms = int(time.time() * 1000)
        if self._time_sync:
             now_ms = self._time_sync.now_ms()
             
        start_time = now_ms - window_ms
        end_time = now_ms
        
        try:
            trades = await self._client.get_user_trades(
                symbol=symbol,
                start_time=start_time,
                end_time=end_time
            )
            
            if not trades or isinstance(trades, dict) and trades.get("error"):
                 err = trades.get("msg") if isinstance(trades, dict) else "Empty"
                 self._telemetry.emit("FILL_SYNC_FAIL", {"symbol": symbol, "error": err})
                 return None
                 
            # Filter matches
            # Trade schema: { "orderId": 123, ... }
            matches = []
            for t in trades:
                match = False
                if order_id and int(t.get("orderId", 0)) == order_id:
                    match = True
                # Fallback: check client oid if present? Fills usually don't have client oid in lite endpoints?
                # userTrades endpoint HAS orderId.
                
                if match:
                    matches.append(t)
                    
            if not matches:
                self._telemetry.emit("FILL_SYNC_EMPTY", {"symbol": symbol, "order_id": order_id})
                return None
                
            # Aggregate
            total_qty = 0.0
            total_cost = 0.0 # qty * price
            total_pnl = 0.0
            total_comm = 0.0
            ts_list = []
            
            for m in matches:
                q = float(m.get("qty", 0))
                p = float(m.get("price", 0))
                pnl = float(m.get("realizedPnl", 0))
                comm = float(m.get("commission", 0))
                
                total_qty += q
                total_cost += (q * p)
                total_pnl += pnl
                total_comm += comm
                ts_list.append(int(m.get("time", 0)))
                
            vwap = total_cost / total_qty if total_qty > 0 else 0.0
            net = total_pnl - total_comm
            
            summary = FillSummary(
                symbol=symbol,
                order_id=order_id,
                qty=total_qty,
                vwap=vwap,
                realized_pnl=total_pnl,
                commission=total_comm,
                net_pnl=net,
                ts_first=min(ts_list) if ts_list else 0,
                ts_last=max(ts_list) if ts_list else 0
            )
            
            # Persist Fills
            self._persistence.insert_order_fills(matches)
            
            self._telemetry.emit("FILL_SYNC_OK", {
                "symbol": symbol, 
                "order_id": order_id, 
                "fills": len(matches),
                "net_pnl": net
            })
            
            return summary
            
        except Exception as e:
            self._telemetry.emit("FILL_SYNC_FAIL", {"symbol": symbol, "error": str(e)})
            return None
