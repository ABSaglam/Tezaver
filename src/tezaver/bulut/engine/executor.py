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
from tezaver.bulut.services.price_round import round_price_to_tick

# ... existing imports ...

class Executor:
    # ... existing init ...
    
    # ... existing execute_plans ...

    async def _execute_single_plan(self, plan: TradePlanV1, ctx):
        # ... existing logic ...
        
        # 0. Idempotency ID (Use generic prefix or default?)
        # For main order we use plan.idempotency_key directly?
        # v0.07 used IdempotencyService.make_client_order_id(plan.idempotency_key) -> "tb_..."
        # v0.09 req: plan keys for main orders unchanged.
        # But we need to use make_client_order_id in general.
        client_order_id = IdempotencyService.make_client_order_id(plan.idempotency_key, prefix="tb_")

        # ... price check ...
        
        # ... decision setup ...
        
        # ... qty calc ...
        
        # ... submit order ...
        
        # ... success handling ...
        
        if status in ["FILLED", "NEW"]:
            ctx.persistence.update_plan_status(plan.idempotency_key, "EXECUTED")
            
            if status == "FILLED":
                avg_price = float(resp.get("avgPrice", 0.0) or current_price)
                
                ctx.telemetry.emit("ORDER_FILLED" if not reduce_only else "CLOSE_ORDER_FILLED", {
                    "symbol": plan.symbol,
                    "order_id": order_id,
                    "avg_price": avg_price,
                    "plan_id": plan.idempotency_key
                })
                
                # --- DB Position Sync ---
                if not reduce_only:
                    # OPEN Logic
                    # Resolve Exit Profile
                    pattern_id = plan.reasons.get("pattern_id") if plan.reasons else None
                    profile = ctx.exit_profile_loader.resolve(plan.symbol, pattern_id)
                    
                    sl_pct = 0.0
                    tp_pct = 0.0
                    if profile:
                        for rule in profile.rules:
                            if rule.type == "fixed_pct":
                                sl_pct = rule.sl_pct or 0.0
                                tp_pct = rule.tp_pct or 0.0
                                break
                    
                    ctx.persistence.upsert_position_open(
                        symbol=plan.symbol,
                        entry_ts=plan.plan_ts,
                        entry_price=avg_price,
                        qty=qty,
                        notional=plan.notional_usdt,
                        sl_pct=sl_pct,
                        tp_pct=tp_pct,
                        pattern_id=pattern_id,
                        exit_profile_id=profile.profile_id if profile else None,
                        exit_params=profile.to_dict() if profile else None
                    )
                    
                    # --- V0.09 Protective Orders ---
                    if self._config.protective_orders_enabled and sl_pct > 0 and tp_pct > 0:
                        try:
                            # 1. Calc Prices
                            sl_price = round_price_to_tick(plan.symbol, avg_price * (1.0 - (sl_pct / 100.0)))
                            tp_price = round_price_to_tick(plan.symbol, avg_price * (1.0 + (tp_pct / 100.0)))
                            
                            # 2. Gen Client IDs
                            sl_cid = IdempotencyService.make_client_order_id(plan.idempotency_key, prefix=self._config.protective_client_id_prefix_sl)
                            tp_cid = IdempotencyService.make_client_order_id(plan.idempotency_key, prefix=self._config.protective_client_id_prefix_tp)
                            
                            # 3. Place Orders (Close All)
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
                            
                        except Exception as e:
                            print(f"[EXECUTOR] Protective Order Failed: {e}")
                            # TODO: Emit failure metric
                    
                else:
                    # CLOSE Logic
                    ctx.persistence.mark_position_closed(
                        symbol=plan.symbol,
                        close_ts=plan.plan_ts,
                        close_price=avg_price
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
