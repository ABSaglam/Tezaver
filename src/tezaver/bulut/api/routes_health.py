# Tezaver Bulut - Health API Routes
"""
Health check endpoints for Bulut API.
"""

from fastapi import APIRouter

from tezaver.bulut.core.context import get_context


router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """
    Basic health check.
    
    Returns:
        {"status": "ok", "service": "tezaver-bulut"}
    """
    return {
        "status": "ok",
        "service": "tezaver-bulut",
        "version": "0.01",
    }


@router.get("/detailed")
async def health_detailed():
    """
    Detailed health check with system state.
    
    Returns:
        Full state including config, pattern pack status, trade lock, etc.
    """
    ctx = get_context()
    state = ctx.state
    
    return {
        "status": "ok",
        "service": "tezaver-bulut",
        "version": "0.01",
        "state": state.to_dict(),
        "config": ctx.config.to_dict(),
        "pattern_pack": ctx.pattern_loader.get_pack_summary(),
        "trade_locked": state.trade_locked,
        "trade_lock_reason": state.trade_lock_reason,
    }
