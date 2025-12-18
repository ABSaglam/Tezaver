# Tezaver Bulut - Trade API Routes
"""
Trade command endpoints for Bulut API.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from tezaver.bulut.core.context import get_context
from tezaver.bulut.schemas.trade_plan_v1 import TradeSide, TradeDecision


router = APIRouter(prefix="/trade", tags=["trade"])


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


@router.post("/command", response_model=TradeCommandResponse)
async def trade_command(request: TradeCommandRequest):
    """
    Execute a trade command.
    
    Returns 409 Conflict if trade is locked.
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


@router.get("/status")
async def get_trade_status():
    """
    Get current trade status (locked/unlocked).
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


@router.get("/positions")
async def get_positions():
    """
    Get open positions.
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
