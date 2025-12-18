# Tezaver Bulut - Executor Engine
"""
Executes trade plans on the exchange.
Handles lifecycle: Plan -> Order -> Fill.
"""

import asyncio
from typing import List, Optional

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.idempotency import IdempotencyService


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
        # 0. Idempotency ID
        client_order_id = IdempotencyService.make_client_order_id(plan.idempotency_key)
        
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
            side = "BUY" # Assumes Long Only for now
            reduce_only = False
            qty = QuantityCalculator.calculate_qty(plan.symbol, current_price, plan.notional_usdt)
            
        elif plan.decision.name == "CLOSE":
            side = "SELL" # Assumes closing Long
            reduce_only = True
            # For Close, we ideally close FULL position.
            # But here we might be given specific qty or "close all"?
            # If notional is 0 in plan, treat as close all?
            # Or fetch position size first?
            # v0.07 Requirement: "SELL MARKET + reduceOnly=true"
            # We need to know HOW MUCH to sell if notional is not provided or if we want full close.
            # Best practice: Check current position size.
            
            try:
                # Fetch position info to get formatted size or current position
                # Optimization: get_position_risk(symbol=...)
                risk_data = await self._client.get_position_risk(symbol=plan.symbol)
                # It returns a list usually
                if risk_data and isinstance(risk_data, list):
                    # Filter for correct position (if multiple modes, usually one for one-way)
                    pos = risk_data[0] # Simplification
                    pos_amt = float(pos.get("positionAmt", 0.0))
                    
                    if pos_amt > 0:
                        qty = abs(pos_amt) # Close full size
                    else:
                        print(f"[EXECUTOR] No OPEN LONG position to close for {plan.symbol}")
                        ctx.persistence.update_plan_status(plan.idempotency_key, "SKIPPED_NO_POS")
                        return
                else:
                    print(f"[EXECUTOR] Failed to fetch position risk for {plan.symbol}")
                    ctx.persistence.update_plan_status(plan.idempotency_key, "FAILED_POS_FETCH")
                    return
            except Exception as e:
                print(f"[EXECUTOR] Exception fetching pos for {plan.symbol}: {e}")
                ctx.persistence.update_plan_status(plan.idempotency_key, "FAILED_POS_FETCH")
                return

        # 3. Validation
        if qty <= 0:
            print(f"[EXECUTOR] Qty 0 for {plan.symbol} (${plan.notional_usdt} @ {current_price})")
            ctx.persistence.update_plan_status(plan.idempotency_key, "FAILED_QTY_ZERO")
            return
            
        print(f"[EXECUTOR] Submitting {plan.symbol} {side} {qty} (Reduce: {reduce_only}) ID: {client_order_id}...")
        
        # 4. Send Order
        resp = await self._client.create_order(
            symbol=plan.symbol,
            side=side,
            qty=qty,
            order_type="MARKET",
            reduce_only=reduce_only,
            client_order_id=client_order_id
        )
        
        if resp.get("error"):
            # Check if error is "Order would start immediately trigger..." or idempotent duplicate?
            # If duplicate, maybe it's already filled?
            print(f"[EXECUTOR] Order Error: {resp}")
            ctx.persistence.update_plan_status(plan.idempotency_key, "FAILED_EXCHANGE_ERROR")
            ctx.telemetry.emit("EXECUTION_ERROR", {
                "symbol": plan.symbol,
                "error": resp,
                "plan_id": plan.idempotency_key
            })
            return
            
        # 5. Success Handling
        order_id = resp.get("orderId")
        status = resp.get("status")
        
        ctx.telemetry.emit("ORDER_SUBMITTED" if not reduce_only else "CLOSE_ORDER_SUBMITTED", {
            "symbol": plan.symbol,
            "order_id": order_id,
            "client_order_id": client_order_id,
            "qty": qty,
            "status": status,
            "reduce_only": reduce_only
        })
        
        if status in ["FILLED", "NEW"]:
            ctx.persistence.update_plan_status(plan.idempotency_key, "EXECUTED")
            
            if status == "FILLED":
                ctx.telemetry.emit("ORDER_FILLED" if not reduce_only else "CLOSE_ORDER_FILLED", {
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
