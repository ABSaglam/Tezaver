# Tezaver Bulut - Autopilot API Routes (P5)
"""
REST endpoints for Autopilot and Pilot Meter.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/autopilot", tags=["autopilot"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


class EnableRequest(BaseModel):
    enabled: bool


@router.get("/status")
async def get_autopilot_status(request: Request):
    """Get autopilot status including enabled state and block reasons."""
    ctx = get_ctx(request)
    
    try:
        autopilot = ctx.autopilot_service
        return autopilot.get_status()
    except Exception as e:
        return {
            "enabled": False,
            "can_operate": False,
            "block_reason": str(e),
            "last_block_reason": None,
            "max_entries_per_cycle": 1
        }


@router.post("/enable")
async def enable_autopilot(request: Request, body: EnableRequest):
    """
    Enable or disable autopilot.
    
    Requires OpsAuth token for mutations.
    """
    ctx = get_ctx(request)
    
    try:
        autopilot = ctx.autopilot_service
        
        if body.enabled:
            success = autopilot.enable()
            if not success:
                status = autopilot.get_status()
                raise HTTPException(
                    status_code=409,
                    detail=f"Cannot enable autopilot: {status.get('block_reason', 'unknown')}"
                )
            return {"enabled": True, "message": "Autopilot enabled"}
        else:
            autopilot.disable()
            return {"enabled": False, "message": "Autopilot disabled"}
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pilot/status")
async def get_pilot_status(request: Request):
    """Get pilot meter status including limit, committed, remaining."""
    ctx = get_ctx(request)
    
    try:
        pilot = ctx.pilot_meter
        return pilot.get_status()
    except Exception as e:
        return {
            "active": False,
            "start_ts": None,
            "end_ts": None,
            "limit_usdt": 50.0,
            "committed_usdt": 0.0,
            "remaining_usdt": 50.0,
            "time_left_hours": 24.0,
            "error": str(e)
        }
