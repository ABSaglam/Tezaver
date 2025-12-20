# Tezaver Bulut - Risk API Routes
"""
Risk status endpoints.
GET /risk/status
"""

from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/risk", tags=["Risk"])

@router.get("/status", summary="TR Risk Status")
async def get_risk_status():
    """
    Get portfolio risk status.
    
    TR Açıklama:
    Portföy risk durumunu, PnL limitlerini ve açık pozisyon yoğunluğunu döndürür.
    
    Returns:
    - Daily PnL vs Limit
    - Entry Halted Status
    - Group Open Counts
    """
    ctx = get_context()
    
    # Reload rules on status check? Optional but good for debug
    if ctx.portfolio_risk:
        ctx.portfolio_risk.reload_rules()
        return ctx.portfolio_risk.get_risk_status()
        
    return {"status": "error", "message": "Risk service not initialized"}
