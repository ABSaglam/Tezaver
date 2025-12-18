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
    commission_asset: str
    net_pnl: float
    ts_first: int
    ts_last: int
    fee_usdt: Optional[float] = None
    fx_rate: Optional[float] = None
    fx_source: Optional[str] = None


class FillSyncService:
    """
    Syncs execution fills to audit PnL accurately.
    """
    def __init__(self, config: BulutConfig, binance_client, telemetry, persistence, time_sync, fx_cache=None):
        self._config = config
        self._client = binance_client
        self._telemetry = telemetry
        self._persistence = persistence
        self._time_sync = time_sync
        self._fx_cache = fx_cache
        
    async def sync_order_fills(
        self, 
        symbol: str, 
        order_id: Optional[int] = None, 
        client_order_id: Optional[str] = None, 
        window_ms: Optional[int] = None
    ) -> Optional[FillSummary]:
        """
        Fetch user trades and aggregate for specific order.
        Returns FillSummary if found, None otherwise.
        """
        if window_ms is None:
            window_ms = getattr(self._config, "fill_sync_window_ms", 600000)

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
            
            if not trades or (isinstance(trades, dict) and trades.get("error")):
                 err = trades.get("msg") if isinstance(trades, dict) else "Empty"
                 self._telemetry.emit("FILL_SYNC_FAIL", {"symbol": symbol, "error": err})
                 return None
                 
            # Filter matches
            matches = []
            for t in trades:
                match = False
                if order_id and int(t.get("orderId", 0)) == order_id:
                    match = True
                
                if match:
                    matches.append(t)
                    
            if not matches:
                # We don't emit EMPTY here because Executor might be retrying
                return None
                
            # Aggregate
            total_qty = 0.0
            total_cost = 0.0 # qty * price
            total_pnl = 0.0
            total_comm = 0.0
            comm_assets = set()
            ts_list = []
            
            for m in matches:
                q = float(m.get("qty", 0))
                p = float(m.get("price", 0))
                pnl = float(m.get("realizedPnl", 0))
                comm = float(m.get("commission", 0))
                asset = m.get("commissionAsset", "USDT")
                
                total_qty += q
                total_cost += (q * p)
                total_pnl += pnl
                total_comm += comm
                comm_assets.add(asset)
                ts_list.append(int(m.get("time", 0)))
                
            vwap = total_cost / total_qty if total_qty > 0 else 0.0
            
            main_asset = "USDT"
            if comm_assets:
                # If multiple assets (rare but possible), prioritize USDT
                if "USDT" in comm_assets:
                    main_asset = "USDT"
                else:
                    main_asset = list(comm_assets)[0]

            # FX Conversion (v0.19)
            fee_usdt = None
            fx_val = None
            fx_src = None
            
            if main_asset == "USDT":
                fee_usdt = total_comm
            elif self._fx_cache:
                 # Try convert total_comm of main_asset to USDT
                 # (If mixed assets, this is approximation using main_asset. 
                 #  Ideally should convert individual fills, but aggregation expects one asset.
                 #  Usually commission asset is uniform per trade unless BNB deduction toggled mid-way.)
                 # Let's use FxRateCache synchronously if rate cached, or rely on async fetch?
                 # FxRateCache methods are async for fetch.
                 # FillSync is async.
                 
                 rate = await self._fx_cache.get_rate(main_asset)
                 if rate:
                     fee, r, s = self._fx_cache.convert_to_usdt(main_asset, total_comm, known_rate=rate)
                     fee_usdt = fee
                     fx_val = r
                     fx_src = s
            
            net = total_pnl
            if fee_usdt is not None:
                net = total_pnl - fee_usdt
            else:
                 # v0.17 legacy behavior: if not USDT and not converted, net = gross pnl.
                 # Alerts handled by persistence/executor?
                 pass

            # Alert if non-USDT and conversion failed
            if main_asset != "USDT" and fee_usdt is None:
                if getattr(self._config, "alert_on_non_usdt_fee", True):
                     self._telemetry.emit("ALERT", {
                         "level": "WARN", 
                         "code": "NON_USDT_FEE_UNACCOUNTED",
                         "message": f"Fill fee in {main_asset} not converted. PnL might be inaccurate.",
                         "details": {"asset": main_asset, "amount": total_comm}
                     })

            summary = FillSummary(
                symbol=symbol,
                order_id=order_id,
                qty=total_qty,
                vwap=vwap,
                realized_pnl=total_pnl,
                commission=total_comm,
                commission_asset=main_asset,
                net_pnl=net,
                ts_first=min(ts_list) if ts_list else 0,
                ts_last=max(ts_list) if ts_list else 0,
                fee_usdt=fee_usdt,
                fx_rate=fx_val,
                fx_source=fx_src
            )
            
            # Persist Fills
            self._persistence.insert_order_fills(matches)
            
            self._telemetry.emit("FILL_SYNC_OK", {
                "symbol": symbol, 
                "order_id": order_id, 
                "fills": len(matches),
                "net_pnl": net,
                "fee_asset": main_asset,
                "fee_usdt": fee_usdt
            })
            
            return summary
            
        except Exception as e:
            self._telemetry.emit("FILL_SYNC_FAIL", {"symbol": symbol, "error": str(e)})
            return None
