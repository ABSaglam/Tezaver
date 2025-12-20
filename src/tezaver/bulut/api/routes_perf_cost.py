# Tezaver Bulut - Performance & Cost API Routes (P13)
"""
REST endpoints for Performance & Cost Guard.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/perf", tags=["Perf"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


class ForceModeRequest(BaseModel):
    """Request body for force mode."""
    mode: str  # NORMAL, DEGRADED, EMERGENCY
    reason: Optional[str] = "Operator override"


@router.get("/status", summary="TR Perf Status")
async def get_perf_status(request: Request):
    """
    Get current performance & cost status.
    
    TR Açıklama:
    Performans ve maliyet koruma modülünün anlık durumunu, bütçe kullanımını ve aktif modunu döndürür.
    """
    ctx = get_ctx(request)
    
    try:
        guard = ctx.perf_cost_guard
        return guard.get_status()
    except Exception as e:
        return {"error": str(e), "mode": "UNKNOWN"}


@router.get("/overrides", summary="TR Active Overrides")
async def get_overrides(request: Request):
    """
    Get current parameter overrides.
    
    TR Açıklama:
    Sistemde aktif olan manuel performans/maliyet parametre geçersiz kılmalarını (override) listeler.
    """
    ctx = get_ctx(request)
    
    try:
        guard = ctx.perf_cost_guard
        return guard.get_overrides()
    except Exception as e:
        return {"error": str(e)}


@router.post("/force_mode", summary="TR Force Perf Mode")
async def force_mode(request: Request, body: ForceModeRequest):
    """
    Force a specific operating mode.
    
    TR Açıklama:
    Performans modunu manuel olarak zorlar (NORMAL, DEGRADED, EMERGENCY).
    Otomatik mod geçişlerini devre dışı bırakır.
    
    Güvenlik:
    - OpsAuth gerektirir (Mutasyon işlemi).
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


@router.post("/clear_force", summary="TR Clear Force Mode")
async def clear_force(request: Request):
    """
    Clear forced mode, return to automatic.
    
    TR Açıklama:
    Manuel zorlanmış modu kaldırır ve sistemi otomatik performans yönetimine döndürür.
    
    Güvenlik:
    - OpsAuth gerektirir.
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


@router.post("/evaluate", summary="TR Trigger Evaluation")
async def evaluate_now(request: Request):
    """
    Manually trigger evaluation.
    
    TR Açıklama:
    Performans ve maliyet metriklerini anlık olarak değerlendirir ve gerekirse mod değişikliği önerir/yapar.
    
    Güvenlik:
    - OpsAuth gerektirir.
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
