# Tezaver Bulut - Health API Routes
"""
Health check endpoints for Bulut API.
"""

from fastapi import APIRouter

from tezaver.bulut.core.context import get_context


router = APIRouter(prefix="/health", tags=["Ops"])


@router.get("", summary="TR Basic Health Check")
async def health_check():
    """
    Basic health check.
    
    TR Açıklama:
    Basit 'ayaktayım' sinyali. Load balancer ve k8s health check için kullanılır.
    
    Returns:
        {"status": "ok", "service": "tezaver-bulut"}
    """
    return {
        "status": "ok",
        "service": "tezaver-bulut",
        "version": "0.01",
    }


@router.get("/detailed", summary="TR Detailed Health Check")
async def health_detailed():
    """
    Detailed health check with system state.
    
    TR Açıklama:
    Sistemin detaylı sağlık durumunu, konfigürasyonu ve kritik bileşenlerin (Time Sync, Trade Lock) durumunu döndürür.
    
    Returns:
        Full state including config, pattern pack status, trade lock, etc.
    """
    ctx = get_context()
    state = ctx.state
    
    # Time Sync Status
    ts_healthy, ts_details = ctx.time_sync.is_healthy()
    
    return {
        "status": "ok",
        "service": "tezaver-bulut",
        "version": "0.01",
        "state": state.to_dict(),
        "config": ctx.config.to_dict(),
        "pattern_pack": ctx.pattern_loader.get_pack_summary(),
        "trade_locked": state.trade_locked,
        "trade_lock_reason": state.trade_lock_reason,
        "time_sync": {
            "healthy": ts_healthy,
            "details": ts_details
        }
    }
