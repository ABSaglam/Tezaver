# Tezaver Bulut - Daemon API Routes
"""
Daemon control endpoints.
"""

from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/daemon", tags=["Ops"])

@router.post("/start", summary="TR Start Scheduler")
async def start_daemon():
    """
    Start the background scheduler.
    
    TR Açıklama:
    Arka plan görev zamanlayıcısını (Scheduler) başlatır.
    
    Güvenlik:
    - OpsAuth gerektirir (Sistem durumu değişikliği).
    """
    ctx = get_context()
    if not ctx.scheduler.is_running():
        await ctx.scheduler.start()
        return {"status": "started", "message": "Scheduler started."}
    return {"status": "already_running"}

@router.post("/stop", summary="TR Stop Scheduler")
async def stop_daemon():
    """
    Stop the background scheduler.
    
    TR Açıklama:
    Arka plan görev zamanlayıcısını durdurur. Piyasadan kopmaya neden olabilir.
    
    Güvenlik:
    - OpsAuth gerektirir.
    """
    ctx = get_context()
    if ctx.scheduler.is_running():
        await ctx.scheduler.stop()
        return {"status": "stopped", "message": "Scheduler stopped."}
    return {"status": "not_running"}

@router.get("/status", summary="TR Scheduler Status")
async def daemon_status():
    """
    Get scheduler status.
    
    TR Açıklama:
    Scheduler'ın çalışıp çalışmadığını ve konfigürasyonunu döndürür.
    """
    ctx = get_context()
    return {
        "running": ctx.scheduler.is_running(),
        "config": {
            "poll_interval": ctx.config.poll_interval_seconds,
            "base_tf": ctx.config.base_tf
        }
    }
