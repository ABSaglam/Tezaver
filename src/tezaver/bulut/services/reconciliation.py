# Tezaver Bulut - Reconciliation Service
"""
Reconciliation service to compare local state with exchange state (restart recovery).
"""

from typing import Dict, Any, List

class ReconciliationService:
    """
    Checks for orphan positions and recovers state.
    """
    
    def __init__(self, ctx):
        self._ctx = ctx
        
    async def reconcile(self) -> Dict[str, Any]:
        """
        Perform reconciliation.
        Returns report dict.
        """
        # 1. Fetch Exchange State
        # Ideally using Executor's client, or one from safety guard?
        # Let's borrow executor's client if available, or create temp?
        # Context has executor lazy loaded.
        
        client = self._ctx.executor._client
        
        report = {
            "orphan_positions": [],
            "db_positions_missing_on_exchange": [],
            "status": "OK"
        }
        
        try:
            # Check Positions
            risk_data = await client.get_position_risk()
            if not risk_data or "error" in risk_data:
                report["status"] = "ERROR_FETCHING_EXCHANGE"
                return report
                
            # Parse Exchange Positions (only non-zero)
            exchange_positions = {}
            for pos in risk_data:
                amt = float(pos.get("positionAmt", 0.0))
                sym = pos.get("symbol")
                if abs(amt) > 0:
                    exchange_positions[sym] = amt
                    
            # 2. Fetch Local DB State
            local_positions = self._ctx.persistence.get_open_positions()
            local_symbols = {p["symbol"] for p in local_positions}
            
            # 3. Compare: Orphan on Exchange (Exists on Exchange, Not in DB)
            for sym, amt in exchange_positions.items():
                if sym not in local_symbols:
                    report["orphan_positions"].append({"symbol": sym, "amt": amt})
                    self._ctx.telemetry.emit("ORPHAN_DETECTED", {"symbol": sym, "amt": amt, "source": "RECONCILE"})
            
            # 4. Compare: Missing on Exchange (Exists in DB, Not on Exchange)
            for sym in local_symbols:
                if sym not in exchange_positions:
                    # Maybe it was closed while we were down?
                    report["db_positions_missing_on_exchange"].append(sym)
                    
            # 5. Protective Order Orphans (v0.09)
            # Fetch open orders?
            open_orders = await client.get_open_orders()
            if open_orders and isinstance(open_orders, list):
                sl_prefix = self._ctx.config.protective_client_id_prefix_sl
                tp_prefix = self._ctx.config.protective_client_id_prefix_tp
                
                for o in open_orders:
                    cid = o.get("clientOrderId", "")
                    sym = o.get("symbol")
                    
                    if cid.startswith(sl_prefix) or cid.startswith(tp_prefix):
                        # It's one of ours.
                        # Do we have an open position for it?
                        if sym not in exchange_positions: # True source of truth
                             # Position closed but order remains -> Orphan
                             print(f"[RECONCILE] Cancelling orphan protective order {o.get('orderId')} for {sym}")
                             await client.cancel_order(symbol=sym, order_id=o.get("orderId"))
                             self._ctx.telemetry.emit("ORPHAN_PROTECTIVE_CANCELLED", {
                                 "symbol": sym,
                                 "order_id": o.get("orderId"),
                                 "client_id": cid
                             })

            self._ctx.telemetry.emit("RECONCILE_REPORT", report)
            return report
            
        except Exception as e:
            report["status"] = f"EXCEPTION: {e}"
            return report
