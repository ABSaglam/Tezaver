from fastapi import APIRouter, HTTPException
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/income", tags=["Income"])

@router.get("/status")
async def get_income_status():
    """Get income sync status."""
    ctx = get_context()
    
    # Check if due (passive check, doesn't force sync)
    # But reload_if_due is logic inside service? 
    # For status we just return DB stats and config.
    
    last_sync = ctx.persistence.get_income_last_sync_ms()
    types_str = getattr(ctx.config, "income_sync_types", "FUNDING_FEE")
    types = [t.strip() for t in types_str.split(",")]
    
    stats = ctx.persistence.get_today_income_sum_utc(types=types)
    
    return {
        "enabled": getattr(ctx.config, "income_sync_enabled", True),
        "last_sync_ms": last_sync,
        "today_funding": stats.get("FUNDING_FEE", 0.0),
        "today_total_income": stats.get("TOTAL", 0.0),
        "non_usdt_count": stats.get("non_usdt_count", 0),
        "checked_types": types
    }

@router.post("/sync")
async def force_sync_income():
    """Force income sync."""
    ctx = get_context()
    try:
        res = await ctx.income_sync.sync_now(force=True)
        return {"status": "success", "data": res}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
