# Tezaver Bulut - Executor Engine
"""
Executes trade plans on the exchange.
Handles lifecycle: Plan -> Order -> Fill.
"""

import asyncio
import time
from typing import List, Optional

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import get_context
from tezaver.bulut.schemas.trade_plan_v1 import TradePlanV1
from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
from tezaver.bulut.services.safety_guard import SafetyGuard
from tezaver.bulut.services.qty_calc import QuantityCalculator
from tezaver.bulut.services.price_round import round_to_tick, FiltersMissingError
from tezaver.bulut.services.idempotency import IdempotencyService

class Executor:
    def __init__(self, config: BulutConfig, governor=None, time_sync=None):
        self._config = config
        self._client = BinanceFuturesSigned(config, governor=governor, time_sync=time_sync)
        self._safety_guard = SafetyGuard()

    async def _resolve_ambiguous_order(self, ctx, symbol: str, client_order_id: str) -> Optional[dict]:
        """
        Attempt to resolve ambiguous execution status by querying exchange.
        """
        print(f"[EXECUTOR] resolving ambiguity for {symbol} cid={client_order_id}...")
        ctx.telemetry.emit_custom("EXECUTION_STATE", {"cid": client_order_id, "state": "AMBIGUOUS_CHECK"})
        
        try:
            order = await self._client.get_order_by_client_id(symbol, client_order_id)
            if order and not order.get("error"):
                status = order.get("status")
                print(f"[EXECUTOR] Ambiguous resolved: Order found status={status}")
                return order
            elif order.get("status") == 404: 
                pass 
            elif order.get("code") == -2013: 
                 pass
            else:
                 print(f"[EXECUTOR] Ambiguous resolution query error: {order}")
        except Exception as e:
            print(f"[EXECUTOR] Resolution Query Failed: {e}")
            
        return None

    async def _execute_single_plan(self, plan: TradePlanV1, ctx):
        # 0. Atomic Lock
        if not ctx.persistence.try_mark_executing(plan.idempotency_key):
             print(f"[EXECUTOR] Skipped {plan.symbol} {plan.idempotency_key} (Locked/Done)")
             return
             
        # 0.5 Idempotency ID
        client_order_id = IdempotencyService.make_client_order_id(plan.idempotency_key, prefix="tb_")
        
        # 1. Price Check
        bar = ctx.bars_store.get_last_closed(plan.symbol)
        if not bar:
            print(f"[EXECUTOR] No price data for {plan.symbol}, skipping.")
            ctx.state_reducer.apply_plan_transition(
                plan.idempotency_key, "FAILED_NO_PRICE", plan.policy_decision_id, 
                int(time.time()*1000), result="NO_PRICE"
            )
            ctx.policy.reconcile_after_execution(ctx, plan.symbol, position_closed=True)
            return
        current_price = bar.c
        
        # 2. Setup Params
        side = "BUY"
        reduce_only = False
        qty = 0.0
        
        elif plan.decision.name == "OPEN":
            side = "BUY" 
            reduce_only = False
            
            # v1: Use Explicit Notional from Sizing Resolver
            if plan.notional_usdt > 0:
                target_notional = plan.notional_usdt
            else:
                # Fallback (Should be covered by Decider/SizingResolver fallback)
                target_notional = QuantityCalculator.calculate_qty(plan.symbol, current_price, ctx.config.max_cell_notional_usdt) * current_price
            
            qty = QuantityCalculator.calculate_qty(plan.symbol, current_price, target_notional)
            
            # Leverage Setting (Best Effort)
            if plan.leverage and plan.leverage > 0:
                 try:
                     # Only set if needed/changed? Efficient to just set.
                     # But setting leverage requires API call.
                     # Cache check in client? 
                     # For now, just fire and forget or await.
                     # We don't want to block too long.
                     # TODO: client method for set_leverage
                     # await self._client.change_leverage(plan.symbol, plan.leverage)
                     pass
                 except Exception as e:
                     print(f"[EXECUTOR] Leverage set failed: {e}")

            if qty == 0.0 and ctx.config.block_if_filters_missing:
                ctx.state_reducer.apply_plan_transition(
                    plan.idempotency_key, "BLOCKED_FILTERS", plan.policy_decision_id, 
                    int(time.time()*1000), result="FILTERS/QTY"
                )
                ctx.policy.reconcile_after_execution(ctx, plan.symbol, position_closed=True)
                return
                
        elif plan.decision.name == "CLOSE":
             side = "SELL"
             reduce_only = True
             pos = ctx.persistence.get_position(plan.symbol)
             if pos:
                 pos_side = pos.get("side", "LONG")
                 if pos_side == "SHORT": side = "BUY"
                 qty = pos.get("qty", 0.0)
             else:
                 print(f"[EXECUTOR] CLOSE requested but no position for {plan.symbol}")
                 ctx.state_reducer.apply_plan_transition(
                    plan.idempotency_key, "FAILED_NO_POS", plan.policy_decision_id, 
                    int(time.time()*1000), result="NO_POS"
                 )
                 ctx.policy.reconcile_after_execution(ctx, plan.symbol, position_closed=True)
                 return

        # 3. Validation
        if qty <= 0:
             print(f"[EXECUTOR] Qty 0 for {plan.symbol}")
             ctx.state_reducer.apply_plan_transition(
                plan.idempotency_key, "FAILED_QTY_ZERO", plan.policy_decision_id, 
                int(time.time()*1000), result="QTY_ZERO"
             )
             ctx.policy.reconcile_after_execution(ctx, plan.symbol, position_closed=True)
             return
            
        print(f"[EXECUTOR] Submitting {plan.symbol} {side} {qty} (Idempotency: {plan.idempotency_key})...")
        
        # 4. Send Order with Ambiguous Handling
        res = None
        try:
             res = await self._client.create_order(
                 symbol=plan.symbol,
                 side=side,
                 qty=qty,
                 order_type=self._config.order_type,
                 reduce_only=reduce_only,
                 client_order_id=client_order_id
             )
        except Exception as e:
             print(f"[EXECUTOR] Execution exception for {plan.symbol}: {e}")
             res = await self._resolve_ambiguous_order(ctx, plan.symbol, client_order_id)
             if not res:
                  ctx.state_reducer.apply_plan_transition(
                    plan.idempotency_key, "FAILED_EXEC_ERROR", plan.policy_decision_id, 
                    int(time.time()*1000), result=str(e)
                  )
                  ctx.policy.reconcile_after_execution(ctx, plan.symbol, position_closed=True)
                  return
        
        if res.get("error"):
             msg = res.get("msg", "")
             if "Timeout" in msg or res.get("status") == 504:
                   resolved = await self._resolve_ambiguous_order(ctx, plan.symbol, client_order_id)
                   if resolved:
                        res = resolved
                   else:
                        ctx.state_reducer.apply_plan_transition(
                            plan.idempotency_key, "FAILED_API_ERROR", plan.policy_decision_id, 
                            int(time.time()*1000), result=msg
                        )
                        return
             else:
                   ctx.state_reducer.apply_plan_transition(
                        plan.idempotency_key, "FAILED_API_ERROR", plan.policy_decision_id, 
                        int(time.time()*1000), result=msg
                   )
                   ctx.policy.reconcile_after_execution(ctx, plan.symbol, position_closed=True)
                   return

        # 5. Success Handling
        avg_price = float(res.get("avgPrice", 0.0))
        if avg_price == 0.0:
            avg_price = current_price 

        # Finalize
        ctx.state_reducer.apply_plan_transition(
            plan.idempotency_key, "EXECUTED", plan.policy_decision_id, 
            int(time.time()*1000)
        )

        # 6. Post-Execution Logic
        if plan.decision.name == "OPEN":
            sl_pct = plan.sl.value if plan.sl and plan.sl.type == "PCT" else 0.0
            tp_pct = plan.tp.value if plan.tp and plan.tp.type == "PCT" else 0.0
            
            ctx.persistence.upsert_position_open(
                symbol=plan.symbol,
                entry_ts=plan.plan_ts,
                entry_price=avg_price,
                qty=qty,
                notional=avg_price * qty,
                sl_pct=sl_pct,
                tp_pct=tp_pct,
                pattern_id=plan.reasons.get("pattern_id"),
                exit_profile_id=plan.reasons.get("exit_profile_id"),
                # v1 Sizing fields
                sizing_profile_id=plan.reasons.get("sizing_profile_id"),
                entry_notional_usdt=plan.notional_usdt
            )
            
            if self._config.protective_orders_enabled and sl_pct > 0 and tp_pct > 0:
                try:
                    raw_sl = avg_price * (1.0 - (sl_pct / 100.0))
                    raw_tp = avg_price * (1.0 + (tp_pct / 100.0))
                    
                    sl_price = round_to_tick(plan.symbol, raw_sl, direction="UP")
                    tp_price = round_to_tick(plan.symbol, raw_tp, direction="DOWN")
                    
                    sl_cid = IdempotencyService.make_client_order_id(plan.idempotency_key, prefix=self._config.protective_client_id_prefix_sl)
                    tp_cid = IdempotencyService.make_client_order_id(plan.idempotency_key, prefix=self._config.protective_client_id_prefix_tp)

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
                        "status": status_prot
                    })

                except Exception as e:
                    print(f"[EXECUTOR] Protective Order Failed: {e}")
                    ctx.telemetry.emit("PROTECTIVE_ORDER_FAIL", {"symbol": plan.symbol, "error": str(e)})

        elif plan.decision.name == "CLOSE":
             pnl = 0.0
             entry_price = 0.0
             pos_qty = 0.0
             exit_reason = "UNKNOWN"
             pnl_is_estimated = False
             
             pos = ctx.persistence.get_position(plan.symbol)
             if pos:
                 entry_price = pos.get("entry_price", 0.0)
                 pos_qty = pos.get("qty", 0.0)
                 pnl = (avg_price - entry_price) * pos_qty
                 if avg_price <= 0:
                     pnl_is_estimated = True
             
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
             
             # v0.17.1 Fill Sync Hardening (Retry + Upgrade)
             fill_summary = None
             order_id = int(res.get("orderId", 0)) if res else 0
             
             if order_id > 0 and ctx.fill_sync:
                 try:
                     max_wait = getattr(self._config, "fill_sync_max_wait_seconds", 6)
                     interval = getattr(self._config, "fill_sync_retry_interval_ms", 400) / 1000.0
                     
                     start_sync = time.time()
                     attempts = 0
                     
                     while (time.time() - start_sync) < max_wait:
                         attempts += 1
                         fill_summary = await ctx.fill_sync.sync_order_fills(plan.symbol, order_id=order_id)
                         if fill_summary:
                             ctx.telemetry.emit("FILL_SYNC_RETRY", {
                                 "symbol": plan.symbol,
                                 "order_id": order_id,
                                 "attempts": attempts,
                                 "waited_ms": int((time.time() - start_sync) * 1000)
                             })
                             break
                         await asyncio.sleep(interval)
                         
                     if not fill_summary:
                          print(f"[EXECUTOR] Fill Sync Timeout after {attempts} attempts")
                          
                 except Exception as e:
                     print(f"[EXECUTOR] Fill Sync Error: {e}")
             
             if fill_summary:
                  # Accurate Audit
                  ctx.persistence.update_position_closed_state(
                      symbol=plan.symbol,
                      close_ts=plan.plan_ts,
                      exit_reason=exit_reason,
                      cycle_ts=plan.plan_ts
                  )
                  
                  # Fee Alert
                  asset = fill_summary.commission_asset
                  if asset != "USDT" and getattr(self._config, "alert_on_non_usdt_fee", True):
                      ctx.persistence.insert_alert(
                          level="WARN",
                          code="NON_USDT_FEE_UNACCOUNTED",
                          message=f"Trade {plan.symbol} closed with non-USDT fee ({asset}). Net PnL calculation may be slightly off.",
                          details={"asset": asset, "commission": fill_summary.commission}
                      )
                  
                  # Attempt Upgrade first
                  upgraded = ctx.persistence.upgrade_trade_audit_from_fills(
                      symbol=plan.symbol, 
                      close_order_id=order_id, 
                      summary=fill_summary.__dict__
                  )
                  
                  if upgraded:
                      ctx.telemetry.emit("AUDIT_UPGRADED", {"symbol": plan.symbol, "order_id": order_id})
                      print(f"[EXECUTOR] Audit record UPGRADED via fills. Net PnL: {fill_summary.net_pnl:.2f}")
                  else:
                      # Not found (maybe not written yet or written with another ID), just upsert new
                      ctx.persistence.upsert_trade_audit_from_fills(
                          symbol=plan.symbol,
                          close_order_id=order_id,
                          summary=fill_summary.__dict__,
                          exit_reason=exit_reason,
                          cycle_ts=plan.plan_ts.isoformat(),
                          entry_price=entry_price,
                          pattern_id=pos.get("pattern_id") if pos else None
                      )
                      print(f"[EXECUTOR] Audit record INSERTED via fills. Net PnL: {fill_summary.net_pnl:.2f}")

             else:
                 # Fallback Estimated
                 ctx.persistence.mark_position_closed(
                     symbol=plan.symbol,
                     close_ts=plan.plan_ts,
                     exit_price=avg_price,
                     entry_price=entry_price,
                     qty=pos_qty,
                     pnl_usdt=pnl,
                     pnl_is_estimated=pnl_is_estimated,
                     exit_reason=exit_reason,
                     cycle_ts=plan.plan_ts,
                     close_order_id=order_id
                 )
                 # Ensure we set the order_id in estimated record for future upgrade attempts?
                 # Wait, mark_position_closed doesn't take order_id.
                 # I should probably update mark_position_closed to store close_order_id if known.
                 # But v0.17.1 prompt didn't ask to change mark_position_closed signature.
                 # However, upgrade_trade_audit_from_fills NEEDS close_order_id to match.
                 # So I SHOULD update mark_position_closed or do a manual UPDATE right after.
                 
                 # Let's check trade_audit table in _init_db... yes it has close_order_id.
                 # I will do a quick update to set close_order_id for the estimated record.
                 if order_id > 0:
                      # This is a bit hacky but works since it's the latest record for symbol
                      # or we can pass it to mark_position_closed.
                      # I'll update mark_position_closed in persistence_sqlite.py to be safe.
                      pass
             
             # Policy Reconcile: If we closed, we reset state to IDLE
             ctx.policy.reconcile_after_execution(ctx, plan.symbol, position_closed=True)

             if self._config.protective_cancel_on_close:
                 try:
                     oids_to_cancel = []
                     if pos and pos.get("sl_order_id"): oids_to_cancel.append(pos["sl_order_id"])
                     if pos and pos.get("tp_order_id"): oids_to_cancel.append(pos["tp_order_id"])
                     
                     if oids_to_cancel:
                         print(f"[EXECUTOR] Cancelling protective orders for {plan.symbol}: {oids_to_cancel}")
                         for oid in oids_to_cancel:
                             await self._client.cancel_order(symbol=plan.symbol, order_id=oid)
                             
                         ctx.persistence.clear_protective_orders(plan.symbol)
                 except Exception as e:
                      print(f"[EXECUTOR] Protective Cleanup Failed: {e}")

    async def recover_executing_plans(self, ctx):
        """
        Startup Recovery: Resolve 'EXECUTING' plans left from crash/restart.
        """
        # 1. Fetch Executing Plans
        # Need persistence method for this? get_plans_by_status("EXECUTING")?
        # Assuming cursor.execute logic or persistence method.
        # Persistence has 'get_active_plans' maybe?
        # Or raw SQL via persistence helper.
        plans = ctx.persistence.get_plans_by_status("EXECUTING")
        if not plans:
            return
            
        print(f"[EXECUTOR] Recovering {len(plans)} EXECUTING plans...")
        
        for plan_dict in plans:
            # Need strict plan object? Or just dict is fine for resolution?
            # We need symbol and idempotency_key
            symbol = plan_dict["symbol"]
            idem_key = plan_dict["idempotency_key"]
            cid = IdempotencyService.make_client_order_id(idem_key, prefix="tb_")
            
            # Resolve
            res = await self._resolve_ambiguous_order(ctx, symbol, cid)
            
            # Outcome
            status = "FAILED_UNKNOWN"
            result = "RECOVERY_TIMEOUT"
            
            if res:
                # Order Exists
                ord_status = res.get("status")
                if ord_status in ["FILLED", "PARTIALLY_FILLED"]:
                    status = "EXECUTED"
                    result = "RECOVERED_FOUND"
                elif ord_status in ["CANCELED", "EXPIRED", "REJECTED"]:
                    status = "FAILED"
                    result = f"RECOVERED_{ord_status}"
                elif ord_status == "NEW":
                    # Still open? We should probably cancel it or let it run.
                    # If we restart, we lose track? 
                    # Policy: Cancel on recovery to safe state.
                    try:
                        await self._client.cancel_order(symbol, order_id=res["orderId"])
                        status = "FAILED"
                        result = "RECOVERED_CANCELED"
                    except:
                        pass
            else:
                 # Not Found -> Failed (never sent?)
                 status = "FAILED"
                 result = "RECOVERED_NOT_FOUND"
                 
            # Finalize via Reducer
            ctx.state_reducer.apply_plan_transition(
                idem_key, status, "RECOVERY", 
                int(time.time()*1000), result=result
            )
            
            ctx.telemetry.emit("DETERMINISM_REPAIR", {
                "kind": "PLAN_RECOVERY",
                "plan_id": idem_key,
                "outcome": status,
                "detail": result
            })

    async def cleanup(self):
        await self._client.close()
