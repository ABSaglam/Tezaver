# Tezaver Bulut - Trade API Routes
"""
Trade command endpoints for Bulut API.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from tezaver.bulut.core.context import get_context
from tezaver.bulut.schemas.trade_plan_v1 import TradeSide, TradeDecision


router = APIRouter(prefix="/trade", tags=["Trading"])


class TradeCommandRequest(BaseModel):
    """Trade command request body."""
    symbol: str
    side: str = "LONG"
    action: str  # "OPEN" or "CLOSE"
    notional_usdt: Optional[float] = None
    idempotency_key: Optional[str] = None


class TradeCommandResponse(BaseModel):
    """Trade command response."""
    status: str
    message: str
    locked: bool
    lock_reason: Optional[str] = None
    plan_id: Optional[str] = None


class CloseRequest(BaseModel):
    symbol: str

@router.post("/close", summary="TR Manual Close Position")
async def close_position(req: CloseRequest):
    """
    Manually create a CLOSE plan.
    
    TR Açıklama:
    Belirtilen sembol için manuel kapatma (CLOSE) emri oluşturur.
    
    Güvenlik:
    - OpsAuth gerektirir (Trade işlemi).
    """
    ctx = get_context()
    
    # 1. Create CLOSE Plan
    # Use idempotency based on timestamp
    now = datetime.now()
    plan = TradePlanV1(
        plan_ts=now,
        symbol=req.symbol,
        side="LONG", # Assuming closing long
        decision="CLOSE",
        notional_usdt=0, # 0 means full close logic in executor
        idempotency_key=f"MANUAL_CLOSE:{req.symbol}:{now.timestamp()}",
        reasons={"manual_trigger": True}
    )
    
    # 2. Persist
    # Manual close is usually "ACCEPTED" immediately for executor to pick up?
    # Or "PROPOSED"?
    # If using /execution/run_once or auto-trade loop...
    # Let's mark ACCEPTED so auto-scheduler or run_once picks it up.
    
    status = "ACCEPTED"
    ctx.persistence.insert_plan(plan, status)
    
    # 3. Trigger immediate execution? 
    # v0.07: "Scheduler... executed accepted plans"
    # If scheduler is running, it will pick up? 
    # Wait, scheduler only picks up plans IT created in that cycle mostly.
    # We modified scheduler loop to: `accepted_plans = [p for p in plans if p.decision.name == "OPEN"]`
    # Warning: Scheduler v0.06 logic only looked at *freshly created* plans.
    # It does NOT poll DB for pending accepted plans.
    
    # So we should probably trigger executor directly here if auto-trade is valid?
    # Or rely on a separate background task.
    # For now, simplistic approach: Try to execute immediately in background task?
    # Or just start a background task here.
    
    if ctx.config.execution_enabled:
         # Async execution
         import asyncio
         asyncio.create_task(ctx.executor.execute_plans([plan]))
    
    return {"status": "submitted", "plan_id": plan.idempotency_key}

@router.post("/command", response_model=TradeCommandResponse, summary="TR Execute Trade Command")
async def trade_command(request: TradeCommandRequest):
    """
    Execute a trade command.
    
    TR Açıklama:
    Manual trade komutu (OPEN/CLOSE) gönderir. Trade kilidi varsa 409 döner.
    
    Returns 409 Conflict if trade is locked.
    
    Güvenlik:
    - OpsAuth gerektirir.
    """
    ctx = get_context()
    
    # Check trade lock
    ctx.update_trade_lock()
    
    if ctx.state.trade_locked:
        # Emit telemetry
        ctx.telemetry.emit_trade_locked(
            request.symbol,
            ctx.state.trade_lock_reason or "UNKNOWN",
        )
        
        # Return 409 Conflict
        raise HTTPException(
            status_code=409,
            detail={
                "status": "locked",
                "message": f"Trade locked: {ctx.state.trade_lock_reason}",
                "locked": True,
                "lock_reason": ctx.state.trade_lock_reason,
            },
        )
    
    # TODO: Implement actual trade execution
    # For now, return stub response
    return TradeCommandResponse(
        status="stub",
        message="Trade execution not implemented. This is a scaffold.",
        locked=False,
        lock_reason=None,
        plan_id=None,
    )


@router.get("/status", summary="TR Trade Engine Status")
async def get_trade_status():
    """
    Get current trade status (locked/unlocked).
    
    TR Açıklama:
    Trade motorunun genel durumunu (kilitli mi, kaç pozisyon açık, notional limiti) döndürür.
    """
    ctx = get_context()
    ctx.update_trade_lock()
    
    return {
        "locked": ctx.state.trade_locked,
        "lock_reason": ctx.state.trade_lock_reason,
        "open_positions": ctx.state.open_positions_count,
        "total_notional_usdt": ctx.state.total_notional_usdt,
        "max_positions": ctx.config.max_open_positions,
        "max_notional_usdt": ctx.config.max_total_notional_usdt,
        "pattern_pack_loaded": ctx.state.pattern_pack_loaded,
    }


@router.get("/positions", summary="TR Open Positions")
async def get_positions():
    """
    Get open positions.
    
    TR Açıklama:
    Sistemdeki tüm açık spot/margin pozisyonları ve detaylarını listeler.
    """
    ctx = get_context()
    
    try:
        positions = ctx.persistence.get_open_positions()
        return {
            "status": "ok",
            "count": len(positions),
            "positions": positions,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "positions": [],
        }
