# Tezaver Bulut - Recovery API Routes (P10)
"""
REST endpoints for Disaster Recovery controls.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/recovery", tags=["recovery"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


@router.get("/status")
async def get_recovery_status(request: Request):
    """Get current recovery status."""
    ctx = get_ctx(request)
    
    try:
        recovery = ctx.restart_recovery
        return recovery.get_status()
    except Exception as e:
        return {
            "status": "ERROR",
            "error": str(e),
            "can_resume": False
        }


class RecoveryRunRequest(BaseModel):
    force: bool = False


@router.post("/run")
async def run_recovery(request: Request, body: Optional[RecoveryRunRequest] = None):
    """
    Run recovery protocol.
    
    Steps:
    1. Exchange position reconcile
    2. DB position reconcile
    3. Plan reconcile
    4. Health checks
    
    Requires OpsAuth token.
    """
    ctx = get_ctx(request)
    
    try:
        recovery = ctx.restart_recovery
        report = recovery.run()
        
        return {
            "success": True,
            "status": report.status.value,
            "blockers": [
                {"code": b.code, "message": b.message, "severity": b.severity}
                for b in report.blockers
            ],
            "stats": report.stats,
            "duration_ms": report.duration_ms,
            "can_resume": report.status.value == "PASS"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/can_resume")
async def can_resume(request: Request):
    """Check if system can resume normal operations."""
    ctx = get_ctx(request)
    
    try:
        recovery = ctx.restart_recovery
        can, reasons = recovery.can_resume()
        
        return {
            "can_resume": can,
            "reasons": reasons
        }
    except Exception as e:
        return {
            "can_resume": False,
            "reasons": [str(e)]
        }


@router.post("/safe_boot")
async def trigger_safe_boot(request: Request):
    """
    Manually trigger safe boot sequence.
    
    Requires OpsAuth token.
    """
    ctx = get_ctx(request)
    
    try:
        recovery = ctx.restart_recovery
        success, message = recovery.safe_boot()
        
        return {
            "success": success,
            "message": message
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
