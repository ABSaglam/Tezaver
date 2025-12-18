# Tezaver Bulut - ExchangeInfo API
"""
API for ExchangeInfo Cache status and control.
"""

from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/exchangeinfo", tags=["exchangeinfo"])

@router.get("/status")
async def get_status():
    """Get cache status."""
    ctx = get_context()
    return ctx.exchangeinfo_cache.get_status()

@router.post("/refresh")
async def refresh_exchange_info():
    """Force refresh of exchange info filters."""
    ctx = get_context()
    ok = await ctx.exchangeinfo_cache.refresh()
    return {
        "ok": ok,
        "status": ctx.exchangeinfo_cache.get_status()
    }
