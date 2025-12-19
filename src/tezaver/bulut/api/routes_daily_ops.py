# Tezaver Bulut - Daily Ops API Routes (P12)
"""
REST endpoints for Day-2 Operations.
"""
from fastapi import APIRouter, Request, HTTPException
from typing import Optional


router = APIRouter(prefix="/ops/daily", tags=["daily_ops"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


@router.get("/today")
async def get_today_report(request: Request):
    """Get today's daily operations report."""
    ctx = get_ctx(request)
    
    try:
        daily = ctx.daily_ops_report
        return daily.get_today_report()
    except Exception as e:
        return {"error": str(e), "date": None}


@router.get("/yesterday")
async def get_yesterday_report(request: Request):
    """Get yesterday's daily operations report."""
    ctx = get_ctx(request)
    
    try:
        daily = ctx.daily_ops_report
        return daily.get_yesterday_report()
    except Exception as e:
        return {"error": str(e), "date": None}


@router.post("/compute")
async def compute_and_save(request: Request, date: Optional[str] = None):
    """
    Compute and save daily report.
    
    Requires OpsAuth token.
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
@router.get("/health/checks")
async def get_health_checks(request: Request, limit: int = 50):
    """Get recent health checks."""
    ctx = get_ctx(request)
    
    try:
        health = ctx.health_check_scheduler
        return health.get_recent_checks(limit=min(limit, 200))
    except Exception as e:
        return []


@router.get("/health/status")
async def get_health_status(request: Request):
    """Get health check scheduler status."""
    ctx = get_ctx(request)
    
    try:
        health = ctx.health_check_scheduler
        return health.get_status()
    except Exception as e:
        return {"error": str(e)}


@router.post("/health/run")
async def run_health_check(request: Request):
    """
    Manually run health check.
    
    Requires OpsAuth token.
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
@router.get("/alerts/top")
async def get_top_alerts(request: Request, limit: int = 20):
    """Get top alerts with routing info."""
    ctx = get_ctx(request)
    
    try:
        router = ctx.alert_router
        return router.get_top_alerts(limit=min(limit, 100))
    except Exception as e:
        return []
