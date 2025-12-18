# Tezaver Bulut - Time Sync API
"""
Time Sync endpoints.
POST /time_sync/refresh
"""

from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/time_sync", tags=["time_sync"])

@router.post("/refresh")
async def refresh_time_sync():
    """
    Force refresh of time sync offset.
    """
    ctx = get_context()
    await ctx.time_sync.refresh()
    
    healthy, details = ctx.time_sync.is_healthy()
    return {
        "status": "success", 
        "refreshed": True,
        "healthy": healthy,
        "details": details
    }
