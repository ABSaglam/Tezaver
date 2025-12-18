# Tezaver Bulut - FX routes
from fastapi import APIRouter
from typing import List, Optional
from pydantic import BaseModel

from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/fx", tags=["fx"])

class RefreshRequest(BaseModel):
    assets: Optional[List[str]] = None

@router.post("/refresh")
async def refresh_rates(req: RefreshRequest):
    """Refreshes FX rates for given assets (or defaults to recent ones)."""
    ctx = get_context()
    cache = ctx.fx_rate_cache
    
    assets = req.assets
    if not assets:
         # Default? For now manual list or just "BNB".
         # Or could query distinct non-usdt assets from DB.
         # For simplicity, default to BNB if empty.
         assets = ["BNB"] 
         
    results = {}
    for asset in assets:
        rate = await cache.refresh_asset(asset)
        results[asset] = rate
        
    return {"status": "ok", "results": results}

@router.post("/recompute_today")
async def recompute_today():
    """Recomputes FX conversion for today's records."""
    ctx = get_context()
    recomputer = ctx.fx_recompute
    
    stats = await recomputer.recompute_today_utc()
    return {"status": "ok", "stats": stats}
