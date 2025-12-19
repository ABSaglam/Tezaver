# Tezaver Bulut - Expansion API Routes (P6)
"""
REST endpoints for Safe Expansion tier management.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/expansion", tags=["expansion"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


class SetTierRequest(BaseModel):
    tier_index: int


@router.get("/status")
async def get_expansion_status(request: Request):
    """Get current expansion status including tier, limit, and step-up eligibility."""
    ctx = get_ctx(request)
    
    try:
        expansion = ctx.expansion_policy
        return expansion.get_status()
    except Exception as e:
        return {
            "enabled": False,
            "current_tier": 0,
            "current_tier_name": "T0_PILOT",
            "limit_usdt": 50.0,
            "max_tier": 2,
            "can_step_up": False,
            "block_reasons": [str(e)],
            "tier_changed_ts": None,
            "tier_history": []
        }


@router.post("/step_up")
async def step_up_tier(request: Request):
    """
    Request step-up to next expansion tier.
    
    Requires OpsAuth token.
    Only succeeds if all gating conditions pass.
    """
    ctx = get_ctx(request)
    
    try:
        expansion = ctx.expansion_policy
        success, error = expansion.step_up()
        
        if not success:
            raise HTTPException(status_code=409, detail=error)
        
        return {
            "success": True,
            "new_tier": expansion.get_current_tier().value,
            "new_limit_usdt": expansion.get_tier_limit()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set_tier")
async def set_tier(request: Request, body: SetTierRequest):
    """
    Forcefully set expansion tier (ops override).
    
    Requires OpsAuth token.
    Use with caution - bypasses normal gating.
    """
    ctx = get_ctx(request)
    
    try:
        expansion = ctx.expansion_policy
        success, error = expansion.set_tier(body.tier_index)
        
        if not success:
            raise HTTPException(status_code=400, detail=error)
        
        return {
            "success": True,
            "tier": body.tier_index,
            "limit_usdt": expansion.get_tier_limit()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
