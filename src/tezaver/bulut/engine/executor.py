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


class Executor:
    """
    Executes trades securely.
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
        self._client = BinanceFuturesSigned(config) # Lazy init session inside client
        
    async def execute_plans(self, plans: List[TradePlanV1]):
        """
        Execute a list of ACCEPTED plans.
        """
        ctx = get_context()
        
        if not plans:
            return
        
        # 1. Safety Guard Check
        allowed, reason = SafetyGuard.check_execution_allowed(ctx)
        
        ctx.telemetry.emit("EXECUTION_GUARD_EVAL", {
            "allowed": allowed,
            "block_reason": reason,
            "plan_count": len(plans)
        })
        
        if not allowed:
            for plan in plans:
                print(f"[EXECUTOR] Blocked {plan.symbol}: {reason}")
                ctx.persistence.update_plan_status(plan.idempotency_key, "BLOCKED_EXECUTION")
                ctx.telemetry.emit("EXECUTION_BLOCKED", {
                    "symbol": plan.symbol,
                    "reason": reason,
                    "plan_id": plan.idempotency_key
                })
            return
            
        # 2. Execution Loop
        for plan in plans:
            await self._execute_single_plan(plan, ctx)

    async def _execute_single_plan(self, plan: TradePlanV1, ctx):
        """Execute one plan."""
        # Get Latest Price from Bars Store
        bar = ctx.bars_store.get_last_closed(plan.symbol)
        if not bar:
            print(f"[EXECUTOR] No price data for {plan.symbol}, skipping.")
            # Maybe block or just skip to retry? Skip implies retry next cycle?
            # But plans are stateful. If we don't change status, scheduler might pick it up again?
            # Scheduler usually picks "new" plans?
            # Currently scheduler creates new plans every cycle.
            # If we skip here, we should probably mark failed to avoid confusion.
            ctx.persistence.update_plan_status(plan.idempotency_key, "FAILED_NO_PRICE")
            return
            
        current_price = bar.c
        
        # Calc Qty
        qty = QuantityCalculator.calculate_qty(
            plan.symbol, 
            current_price, 
            plan.notional_usdt
        )
        
        if qty <= 0:
            print(f"[EXECUTOR] Qty 0 for {plan.symbol} (${plan.notional_usdt} @ {current_price})")
            ctx.persistence.update_plan_status(plan.idempotency_key, "FAILED_QTY_ZERO")
            return
            
        print(f"[EXECUTOR] Submitting {plan.symbol} {plan.side.name} {qty} @ ~{current_price}...")
        
        # Send Order
        resp = await self._client.create_order(
            symbol=plan.symbol,
            side=plan.side.name, # LONG -> BUY
            qty=qty,
            order_type="MARKET" # V0.06 supports market only
        )
        
        if resp.get("error"):
            print(f"[EXECUTOR] Order Error: {resp}")
            ctx.persistence.update_plan_status(plan.idempotency_key, "FAILED_EXCHANGE_ERROR")
            ctx.telemetry.emit("EXECUTION_ERROR", {
                "symbol": plan.symbol,
                "error": resp,
                "plan_id": plan.idempotency_key
            })
            return
            
        # Success (at least submission)
        order_id = resp.get("orderId")
        status = resp.get("status")
        
        ctx.telemetry.emit("ORDER_SUBMITTED", {
            "symbol": plan.symbol,
            "order_id": order_id,
            "qty": qty,
            "status": status,
            "resp": resp
        })
        
        if status == "FILLED" or status == "NEW":
            ctx.persistence.update_plan_status(plan.idempotency_key, "EXECUTED")
            
            # If FILLED, emit fill event
            if status == "FILLED":
                ctx.telemetry.emit("ORDER_FILLED", {
                    "symbol": plan.symbol,
                    "order_id": order_id,
                    "avg_price": resp.get("avgPrice"),
                    "plan_id": plan.idempotency_key
                })
        else:
            # Partial/Rejected?
            pass
            
    async def cleanup(self):
        await self._client.close()
