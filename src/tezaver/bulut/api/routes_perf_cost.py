# Tezaver Bulut - Performance & Cost API Routes (P13)
"""
REST endpoints for Performance & Cost Guard.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/perf", tags=["perf_cost"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


class ForceModeRequest(BaseModel):
    """Request body for force mode."""
    mode: str  # NORMAL, DEGRADED, EMERGENCY
    reason: Optional[str] = "Operator override"


@router.get("/status")
async def get_perf_status(request: Request):
    """Get current performance & cost status."""
    ctx = get_ctx(request)
    
    try:
        guard = ctx.perf_cost_guard
        return guard.get_status()
    except Exception as e:
        return {"error": str(e), "mode": "UNKNOWN"}


@router.get("/overrides")
async def get_overrides(request: Request):
    """Get current parameter overrides."""
    ctx = get_ctx(request)
    
    try:
        guard = ctx.perf_cost_guard
        return guard.get_overrides()
    except Exception as e:
        return {"error": str(e)}


@router.post("/force_mode")
async def force_mode(request: Request, body: ForceModeRequest):
    """
    Force a specific operating mode.
    
    Requires OpsAuth token.
    
    Modes: NORMAL, DEGRADED, EMERGENCY
    """
    ctx = get_ctx(request)
    
    try:
        from tezaver.bulut.core.perf_cost_guard import PerfCostMode
        
        mode_map = {
            "NORMAL": PerfCostMode.NORMAL,
            "DEGRADED": PerfCostMode.DEGRADED,
            "EMERGENCY": PerfCostMode.EMERGENCY
        }
        
        mode_str = body.mode.upper()
        if mode_str not in mode_map:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {body.mode}")
        
        guard = ctx.perf_cost_guard
        success = guard.force_mode(mode_map[mode_str], body.reason or "Operator override")
        
        return {
            "success": success,
            "mode": mode_str,
            "reason": body.reason
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear_force")
async def clear_force(request: Request):
    """
    Clear forced mode, return to automatic.
    
    Requires OpsAuth token.
    """
    ctx = get_ctx(request)
    
    try:
        guard = ctx.perf_cost_guard
        success = guard.clear_force()
        
        return {
            "success": success,
            "message": "Forced mode cleared, returning to automatic"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_now(request: Request):
    """
    Manually trigger evaluation.
    
    Requires OpsAuth token.
    """
    ctx = get_ctx(request)
    
    try:
        guard = ctx.perf_cost_guard
        status = guard.evaluate()
        
        return {
            "success": True,
            "mode": status.mode.value,
            "reasons": status.reasons,
            "recommendations": {
                "scan_topk": status.recommendations.scan_topk,
                "poll_interval_ms": status.recommendations.poll_interval_ms,
                "catchup_bars_max": status.recommendations.catchup_bars_max
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
