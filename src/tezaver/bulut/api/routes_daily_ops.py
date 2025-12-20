# Tezaver Bulut - Daily Ops API Routes (P12)
"""
REST endpoints for Day-2 Operations.
"""
from fastapi import APIRouter, Request, HTTPException
from typing import Optional


router = APIRouter(prefix="/ops/daily", tags=["Ops"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


@router.get("/today", summary="TR Today Ops Report")
async def get_today_report(request: Request):
    """
    Get today's daily operations report.
    
    TR Açıklama:
    Bugüne ait operasyonel özet raporu (PnL, Trade sayıları, Alertler, Anomaliler) döndürür.
    Cache'den veya canlı hesaplamadan gelebilir.
    """
    ctx = get_ctx(request)
    
    try:
        daily = ctx.daily_ops_report
        return daily.get_today_report()
    except Exception as e:
        return {"error": str(e), "date": None}


@router.get("/yesterday", summary="TR Yesterday Ops Report")
async def get_yesterday_report(request: Request):
    """
    Get yesterday's daily operations report.
    
    TR Açıklama:
    Düne ait tamamlanmış operasyon raporunu döndürür. Arşivlenmiş veridir.
    """
    ctx = get_ctx(request)
    
    try:
        daily = ctx.daily_ops_report
        return daily.get_yesterday_report()
    except Exception as e:
        return {"error": str(e), "date": None}


@router.post("/compute", summary="TR Compute Ops Report")
async def compute_and_save(request: Request, date: Optional[str] = None):
    """
    Compute and save daily report.
    
    TR Açıklama:
    Günlük raporu manuel olarak tetikler ve kaydeder. Eksik raporları tamamlamak veya snaphot almak için kullanılır.
    
    Güvenlik:
    - OpsAuth gerektirir.
    """
    ctx = get_ctx(request)
    
    try:
        daily = ctx.daily_ops_report
        
        if date:
            from datetime import datetime, timezone
            # Compute for specific date not currently supported
            summary = daily.compute_today_summary()
        else:
            summary = daily.compute_today_summary()
        
        saved = daily.save_report(summary)
        
        return {
            "success": saved,
            "date": summary.date,
            "report": daily._summary_to_dict(summary)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoints
@router.get("/health/checks", summary="TR Health Check History")
async def get_health_checks(request: Request, limit: int = 50):
    """
    Get recent health checks.
    
    TR Açıklama:
    Sistem sağlık kontrollerinin tarihçesini listeler. Anomalileri ve alınan aksiyonları gösterir.
    """
    ctx = get_ctx(request)
    
    try:
        health = ctx.health_check_scheduler
        return health.get_recent_checks(limit=min(limit, 200))
    except Exception as e:
        return []


@router.get("/health/status", summary="TR Health Scheduler Status")
async def get_health_status(request: Request):
    """
    Get health check scheduler status.
    
    TR Açıklama:
    Sağlık kontrolcüsünün (Scheduler) çalışma durumunu ve son çalışma zamanını döndürür.
    """
    ctx = get_ctx(request)
    
    try:
        health = ctx.health_check_scheduler
        return health.get_status()
    except Exception as e:
        return {"error": str(e)}


@router.post("/health/run", summary="TR Run Health Check")
async def run_health_check(request: Request):
    """
    Manually run health check.
    
    TR Açıklama:
    Sistem sağlık kontrolünü (Health Check) anlık olarak başlatır.
    
    Güvenlik:
    - OpsAuth gerektirir (Sistemi yorabilir veya durum değiştirebilir).
    """
    ctx = get_ctx(request)
    
    try:
        health = ctx.health_check_scheduler
        result = health.run_check()
        
        return {
            "success": True,
            "result": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Alert endpoints
@router.get("/alerts/top", summary="TR Top Alerts")
async def get_top_alerts(request: Request, limit: int = 20):
    """
    Get top alerts with routing info.
    
    TR Açıklama:
    Sistemdeki en önemli (BLOCK/WARN) alarmları ve yönlendirme bilgisini listeler.
    """
    ctx = get_ctx(request)
    
    try:
        router = ctx.alert_router
        return router.get_top_alerts(limit=min(limit, 100))
    except Exception as e:
        return []
