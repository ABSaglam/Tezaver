# Tezaver Bulut - Daemon API Routes
"""
Daemon control endpoints.
"""

from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/daemon", tags=["daemon"])

@router.post("/start")
async def start_daemon():
    """Start the background scheduler."""
    ctx = get_context()
    if not ctx.scheduler.is_running():
        await ctx.scheduler.start()
        return {"status": "started", "message": "Scheduler started."}
    return {"status": "already_running"}

@router.post("/stop")
async def stop_daemon():
    """Stop the background scheduler."""
    ctx = get_context()
    if ctx.scheduler.is_running():
        await ctx.scheduler.stop()
        return {"status": "stopped", "message": "Scheduler stopped."}
    return {"status": "not_running"}

@router.get("/status")
async def daemon_status():
    """Get scheduler status."""
    ctx = get_context()
    return {
        "running": ctx.scheduler.is_running(),
        "config": {
            "poll_interval": ctx.config.poll_interval_seconds,
            "base_tf": ctx.config.base_tf
        }
    }
