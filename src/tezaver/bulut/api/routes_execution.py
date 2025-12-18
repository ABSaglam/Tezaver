# Tezaver Bulut - Execution API Routes
"""
Execution control and monitoring endpoints.
"""

from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/execution", tags=["execution"])

@router.get("/status")
async def execution_status():
    """Get execution system status."""
    ctx = get_context()
    
    # Check guard status (simulation)
    from tezaver.bulut.services.safety_guard import SafetyGuard
    allowed, reason = SafetyGuard.check_execution_allowed(ctx)
    
    return {
        "enabled": ctx.config.execution_enabled,
        "mode": ctx.config.mode,
        "require_arm": ctx.config.require_arm,
        "armed": bool(ctx.config.arm_token),
        "safety_check": {
            "allowed": allowed,
            "block_reason": reason
        }
    }

@router.post("/run_once")
async def run_execution_cycle():
    """
    Force run execution for PENDING acceptced plans?
    Or just trigger executor on latest plans?
    For v0.06, maybe just retry execution on existing ACCEPTED plans in DB that are not yet EXECUTED?
    Not implemented in persistence yet (fetching ACCEPTED but not EXECUTED).
    So this is a stub or advanced feature.
    Let's leave stub message.
    """
    return {"status": "stub", "message": "Manual execution trigger not fully implemented yet."}
