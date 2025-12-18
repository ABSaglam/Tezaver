from fastapi import APIRouter
from typing import List, Optional
from tezaver.bulut.core.context import get_context
router = APIRouter()

@router.get("/summary")
async def get_ui_summary():
    """Aggregate summary for UI Command Center."""
    ctx = get_context()
    if not ctx: return {}
    
    positions = []
    if hasattr(ctx, "persistence"):
         positions = ctx.persistence.get_open_positions()
         
    plans = []
    if hasattr(ctx, "persistence"):
        plans = ctx.persistence.get_latest_plans(limit=50)
    
    risk = {}
    if hasattr(ctx, "portfolio_risk"):
         risk = ctx.portfolio_risk.get_status_snapshot()
         
    status = {
        "mode": ctx.config.mode,
        "armed": ctx.execution_service.is_armed() if hasattr(ctx, "execution_service") else False,
        "ts": getattr(ctx, "time_sync", ctx.state).now_iso() if hasattr(ctx, "time_sync") else datetime.now(timezone.utc).isoformat()
    }
    
    return {
        "positions_open": positions,
        "plans_latest": plans,
        "risk_status": risk,
        "status": status,
        "ranking_latest": [] # Placeholder until ranking service exposed
    }

@router.get("/bars/series")
async def get_bars_series(symbol: str, tf: str = "15m", limit: int = 300):
    """Get OHLCV series for a symbol."""
    ctx = get_context()
    if not ctx: return {"error": "Context not ready"}
    
    if hasattr(ctx, "bars_store"):
        # Explicit access to internal memory store
        # BarsStore has 'get_series(symbol)' but schema might differ.
        # It likely returns list of dicts or DataFrame.
        # Assuming get_series returns standard list of dicts.
        try:
            return ctx.bars_store.get_series(symbol, limit=limit)
        except Exception as e:
            return {"error": str(e)}
    return {"error": "Bars store not found"}

@router.get("/audit/latest")
async def get_audit_latest(limit: int = 50):
    """Get recent trade audits."""
    ctx = get_context()
    if not ctx: return []
    if hasattr(ctx, "persistence"):
        return ctx.persistence.get_latest_audit(limit=limit)
    return []

@router.get("/income/today")
async def get_income_today():
    """Get today's income summary."""
    ctx = get_context()
    if not ctx: return {}
    if hasattr(ctx, "persistence"):
        return ctx.persistence.get_today_income_sum_utc()
    return {}

@router.get("/fx/rates")
async def get_fx_rates():
    """Get cached FX rates."""
    ctx = get_context()
    if not ctx: return {}
    if hasattr(ctx, "persistence"):
        return ctx.persistence.get_all_fx_rates()
    return []
