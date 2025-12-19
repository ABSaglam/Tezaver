# Tezaver Bulut - Allocation API Routes (P7)
"""
REST endpoints for Capital Allocation Engine.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/allocation", tags=["allocation"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


@router.get("/status")
async def get_allocation_status(request: Request):
    """Get current allocation status including usage and limits."""
    ctx = get_ctx(request)
    
    try:
        engine = ctx.allocation_engine
        return engine.get_status()
    except Exception as e:
        return {
            "tier_limit_usdt": 50.0,
            "total_used_usdt": 0.0,
            "remaining_usdt": 50.0,
            "tier_usage_pct": 0.0,
            "symbol_usage": {},
            "pattern_usage": {},
            "error": str(e)
        }


@router.post("/recompute")
async def recompute_allocations(request: Request):
    """
    Recompute allocations from current positions.
    
    Requires OpsAuth token.
    """
    ctx = get_ctx(request)
    
    try:
        engine = ctx.allocation_engine
        
        # Reset and recompute from open positions
        engine.reset()
        
        # Get open positions and recompute
        positions = ctx.persistence.get_positions(status="OPEN")
        for pos in positions:
            symbol = pos.get("symbol", "")
            notional = pos.get("notional_usdt", 0.0)
            pattern = pos.get("pattern_id", None)
            engine.commit_allocation(symbol, pattern, notional)
        
        return {
            "success": True,
            "positions_counted": len(positions),
            "status": engine.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decisions/latest")
async def get_latest_decisions(request: Request, limit: int = 100):
    """Get latest allocation decisions."""
    ctx = get_ctx(request)
    
    try:
        engine = ctx.allocation_engine
        return engine.get_decisions(limit=min(limit, 500))
    except Exception as e:
        return []


class AllocationCheckRequest(BaseModel):
    symbol: str
    pattern: Optional[str] = None
    notional_usdt: float


@router.post("/check")
async def check_allocation(request: Request, body: AllocationCheckRequest):
    """
    Check if an allocation would be allowed.
    
    Does not commit - just checks.
    """
    ctx = get_ctx(request)
    
    try:
        engine = ctx.allocation_engine
        decision = engine.check_allocation(
            symbol=body.symbol,
            pattern=body.pattern,
            notional_usdt=body.notional_usdt
        )
        
        return {
            "allowed": decision.allowed,
            "deny_reason": decision.deny_reason,
            "symbol_usage_pct": decision.symbol_usage_pct,
            "pattern_usage_pct": decision.pattern_usage_pct,
            "tier_usage_pct": decision.tier_usage_pct
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
