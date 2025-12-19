# Tezaver Bulut - Kill Switch API Routes (P9)
"""
REST endpoints for Kill Switch emergency controls.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/kill_switch", tags=["kill_switch"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


class KillSwitchActionRequest(BaseModel):
    reason: str
    actor: Optional[str] = "ops_api"


@router.get("/status")
async def get_kill_switch_status(request: Request):
    """Get current kill switch status."""
    ctx = get_ctx(request)
    
    try:
        ks = ctx.kill_switch
        return ks.get_status()
    except Exception as e:
        return {
            "state": "UNKNOWN",
            "error": str(e)
        }


@router.post("/halt")
async def halt(request: Request, body: KillSwitchActionRequest):
    """
    HALT: Stop new entries, disable autopilot.
    
    Requires OpsAuth token.
    """
    ctx = get_ctx(request)
    
    try:
        ks = ctx.kill_switch
        success, message = ks.halt(body.reason, body.actor or "ops_api")
        
        return {
            "success": success,
            "message": message,
            "status": ks.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/safe")
async def safe_mode(request: Request, body: KillSwitchActionRequest):
    """
    SAFE: Keep protective orders, monitor only.
    
    Requires OpsAuth token.
    """
    ctx = get_ctx(request)
    
    try:
        ks = ctx.kill_switch
        success, message = ks.safe(body.reason, body.actor or "ops_api")
        
        return {
            "success": success,
            "message": message,
            "status": ks.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flatten")
async def flatten(request: Request, body: KillSwitchActionRequest):
    """
    FLATTEN: Close all positions with reduceOnly market orders.
    
    Requires OpsAuth token.
    CRITICAL: This will close ALL open positions!
    """
    ctx = get_ctx(request)
    
    try:
        ks = ctx.kill_switch
        success, message, plans = ks.flatten(body.reason, body.actor or "ops_api")
        
        return {
            "success": success,
            "message": message,
            "close_plans": plans,
            "status": ks.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume")
async def resume(request: Request, body: KillSwitchActionRequest):
    """
    RESUME: Return to normal operations.
    
    Requires OpsAuth token.
    """
    ctx = get_ctx(request)
    
    try:
        ks = ctx.kill_switch
        success, message = ks.resume(body.reason, body.actor or "ops_api")
        
        return {
            "success": success,
            "message": message,
            "status": ks.get_status()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events")
async def get_events(request: Request, limit: int = 20):
    """Get recent kill switch events."""
    ctx = get_ctx(request)
    
    try:
        ks = ctx.kill_switch
        return ks.get_events(limit=min(limit, 100))
    except Exception as e:
        return []


@router.post("/export")
async def export_incident(request: Request, body: KillSwitchActionRequest):
    """
    Manually export incident bundle.
    
    Requires OpsAuth token.
    """
    ctx = get_ctx(request)
    
    try:
        ks = ctx.kill_switch
        ks._auto_export_incident(
            body.reason or "manual_export",
            body.actor or "ops_api",
            "MANUAL"
        )
        
        return {
            "success": True,
            "message": "Incident bundle exported"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
