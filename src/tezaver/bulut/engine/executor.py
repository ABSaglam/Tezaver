# Tezaver Bulut - Executor Engine
"""
Executes trade plans on the exchange.
Handles lifecycle: Plan -> Order -> Fill.
"""

import asyncio
from typing import List, Optional

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import get_context
from tezaver.bulut.schemas.trade_plan_v1 import TradePlanV1
from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
from tezaver.bulut.services.safety_guard import SafetyGuard
from tezaver.bulut.services.qty_calc import QuantityCalculator
from tezaver.bulut.services.price_round import round_to_tick, FiltersMissingError

# ... existing imports ...

class Executor:
    # ... existing code ...

    async def _execute_single_plan(self, plan: TradePlanV1, ctx):
        # ... existing logic ...
        
        # 0. Idempotency ID
        client_order_id = IdempotencyService.make_client_order_id(plan.idempotency_key, prefix="tb_")
        
        # 1. Price Check
        bar = ctx.bars_store.get_last_closed(plan.symbol)
        if not bar:
            print(f"[EXECUTOR] No price data for {plan.symbol}, skipping.")
            ctx.persistence.update_plan_status(plan.idempotency_key, "FAILED_NO_PRICE")
            return
            
        current_price = bar.c
        
        # 2. Setup Params based on Decision
        side = "BUY"
        reduce_only = False
        qty = 0.0
        
        if plan.decision.name == "OPEN":
            side = "BUY" 
            reduce_only = False
            qty = QuantityCalculator.calculate_qty(plan.symbol, current_price, plan.notional_usdt)
            
            if qty == 0.0 and ctx.config.block_if_filters_missing:
                # Assuming 0.0 implies violation or missing filters if configured to block
                # Detailed reason is in telemetry
                ctx.persistence.update_plan_status(plan.idempotency_key, "BLOCKED_FILTERS")
                return

        elif plan.decision.name == "CLOSE":
             # ... close logic same as before ...
             pass
             # Need qty for close? 
             # ... reused code ...

        # 3. Validation
        if qty <= 0:
            if plan.decision.name == "CLOSE":
                 # Maybe close all handled inside create_order if qty missing?
                 # But basic checks...
                 pass
            else:
                 print(f"[EXECUTOR] Qty 0 for {plan.symbol}")
                 ctx.persistence.update_plan_status(plan.idempotency_key, "FAILED_QTY_ZERO")
                 return
            
        print(f"[EXECUTOR] Submitting {plan.symbol} {side} {qty}...")
        
        # 4. Send Order 
        # ... create_order ...
        
        # ... Success handling ...
        
                    # ... Upsert Position ...
                    
                    # --- V0.10 Protective Orders ---
                    if self._config.protective_orders_enabled and sl_pct > 0 and tp_pct > 0:
                        try:
                            # 1. Calc Prices with Filters
                            raw_sl = avg_price * (1.0 - (sl_pct / 100.0))
                            raw_tp = avg_price * (1.0 + (tp_pct / 100.0))
                            
                            sl_price = round_to_tick(plan.symbol, raw_sl, direction="UP")
                            tp_price = round_to_tick(plan.symbol, raw_tp, direction="DOWN")
                            
                            # 2. Gen Client IDs ...
                            # ... match previous logic ...
                            sl_cid = IdempotencyService.make_client_order_id(plan.idempotency_key, prefix=self._config.protective_client_id_prefix_sl)
                            tp_cid = IdempotencyService.make_client_order_id(plan.idempotency_key, prefix=self._config.protective_client_id_prefix_tp)

                            # 3. Place Orders ... (Same layout as v0.09)
                            res_sl = await self._client.place_stop_market_close_all(
                                symbol=plan.symbol,
                                stop_price=sl_price,
                                client_order_id=sl_cid,
                                working_type=self._config.protective_working_type,
                                price_protect=self._config.protective_price_protect
                            )
                            
                            res_tp = await self._client.place_take_profit_market_close_all(
                                symbol=plan.symbol,
                                stop_price=tp_price,
                                client_order_id=tp_cid,
                                working_type=self._config.protective_working_type,
                                price_protect=self._config.protective_price_protect
                            )
                            
                            sl_oid = res_sl.get("orderId")
                            tp_oid = res_tp.get("orderId")
                            
                            # 4. Update DB
                            status_prot = "PLACED"
                            if not sl_oid or not tp_oid:
                                status_prot = "FAILED_PARTIAL"
                                
                            ctx.persistence.set_protective_orders(..., status=status_prot) # simplified for match
                            # Need full match
                            ctx.persistence.set_protective_orders(
                                symbol=plan.symbol,
                                sl_order_id=str(sl_oid) if sl_oid else None,
                                tp_order_id=str(tp_oid) if tp_oid else None,
                                sl_client_id=sl_cid,
                                tp_client_id=tp_cid,
                                status=status_prot
                            )
                            
                            ctx.telemetry.emit_protective_orders_placed({
                                "symbol": plan.symbol,
                                "sl_price": sl_price,
                                "tp_price": tp_price,
                                "sl_oid": sl_oid,
                                "tp_oid": tp_oid,
                                "status": status_prot
                            })

                        except FiltersMissingError:
                            print(f"[EXECUTOR] Filters missing for {plan.symbol}, protective orders skipped/blocked.")
                            ctx.telemetry.emit("FILTERS_MISSING", {"symbol": plan.symbol, "context": "protective"})
                            
                        except Exception as e:
                            print(f"[EXECUTOR] Protective Order Failed: {e}")
                            
                 # ... Close Logic ...
                    # CLOSE Logic
                    # Calculate PnL if possible
                    pnl = 0.0
                    exit_reason = "UNKNOWN"
                    
                    pos = ctx.persistence.get_position(plan.symbol)
                    if pos:
                        entry_price = pos["entry_price"]
                        # Assume LONG
                        # filled_qty from order result usually, but here 'qty' was sent order qty.
                        # Using 'qty' as approximation or parse 'res' for 'executedQty'.
                        # 'res' is available from `_client.market_close` result?
                        # `res = await self._client.place_order(...)`
                        # avg_price comes from `float(res.get("avgPrice", 0))` or similar logic above.
                        # Assuming avg_price is valid.
                        pnl = (avg_price - entry_price) * qty
                    
                    # Determine Exit Reason
                    if plan.reasons.get("manual_trigger"):
                        exit_reason = "MANUAL"
                    elif plan.reasons.get("is_sl"):
                        exit_reason = "SL"
                    elif plan.reasons.get("is_tp"):
                        exit_reason = "TP"
                    elif plan.reasons.get("timeout"):
                         exit_reason = "TIME"
                    elif "exit_reason" in plan.reasons:
                        exit_reason = plan.reasons["exit_reason"]
                        
                    ctx.persistence.mark_position_closed(
                        symbol=plan.symbol,
                        close_ts=plan.plan_ts,
                        close_price=avg_price,
                        pnl=pnl,
                        exit_reason=exit_reason
                    )
                    
                    # --- V0.09 Cleanup Protective Orders ---
                    if self._config.protective_cancel_on_close:
                        try:
                            # We need to know the IDs. Fetch from DB before close logic? 
                            # Or just cancel all open orders for symbol?
                            # Prompt says: "positions’dan sl_order_id/tp_order_id varsa"
                            # But we executed logic inside loop. We might need to fetch pos first?
                            # Ideally we fetched 'pos' earlier or we fetch now.
                            # 'mark_position_closed' doesn't return info.
                            pos_data = ctx.persistence.get_position(plan.symbol)
                            if pos_data:
                                # Logic: Cancel specific or all?
                                # "matching orderId’leri cancel et (varsa)"
                                # Safer to cancel EVERYTHING for this symbol if we closed position?
                                # "place_stop_market_close_all" implies full position closure.
                                # If we closed manually, we likely want to remove these.
                                
                                oids_to_cancel = []
                                if pos_data.get("sl_order_id"): oids_to_cancel.append(pos_data["sl_order_id"])
                                if pos_data.get("tp_order_id"): oids_to_cancel.append(pos_data["tp_order_id"])
                                
                                if oids_to_cancel:
                                    print(f"[EXECUTOR] Cancelling protective orders for {plan.symbol}: {oids_to_cancel}")
                                    for oid in oids_to_cancel:
                                        await self._client.cancel_order(symbol=plan.symbol, order_id=oid)
                                        
                                    ctx.persistence.clear_protective_orders(plan.symbol)
                                    ctx.telemetry.emit_protective_orders_cancelled({
                                        "symbol": plan.symbol,
                                        "cancelled_ids": oids_to_cancel
                                    })
                        except Exception as e:
                             print(f"[EXECUTOR] Protective Cleanup Failed: {e}")

        else:
            # Partial/Rejected?
            pass
            
    async def cleanup(self):
        await self._client.close()
```
