# Tezaver Bulut - FastAPI Backend
"""
Main FastAPI application for Tezaver Bulut.

Run with:
    uvicorn tezaver.bulut.app_backend:app --reload --port 8000
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager

from tezaver.bulut.core.context import bootstrap_context
from tezaver.bulut.api.routes_health import router as health_router
from tezaver.bulut.api.routes_ranking import router as ranking_router
from tezaver.bulut.api.routes_trade import router as trade_router
from tezaver.bulut.api.routes_bars import router as bars_router
from tezaver.bulut.api.routes_daemon import router as daemon_router
from tezaver.bulut.api.routes_plans import router as plans_router
from tezaver.bulut.api.routes_execution import router as execution_router
from tezaver.bulut.api.routes_reconcile import router as reconcile_router
from tezaver.bulut.api.routes_positions import router as positions_router
from tezaver.bulut.api.routes_exit_profiles import router as exit_profiles_router
from tezaver.bulut.api.routes_exchangeinfo import router as exchangeinfo_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("[BULUT] Starting Tezaver Bulut v0.10...")
    ctx = bootstrap_context()
    
    # Try to load pattern pack
    if ctx.load_pattern_pack():
        print(f"[BULUT] Pattern pack loaded: {ctx.state.pattern_pack_id}")
    else:
        print("[BULUT] No pattern pack found - trade locked")
    
    # Init lazy services
    _ = ctx.universe_source.load()
    _ = ctx.bars_store
    
    # ExchangeInfo Refresh (v0.10)
    if ctx.config.exchangeinfo_refresh_on_start:
         print("[BULUT] Refreshing ExchangeInfo Filters...")
         await ctx.exchangeinfo_cache.refresh()

    # Start Scheduler (Daemon)
    print("[BULUT] Starting auto-scheduler...")
    await ctx.scheduler.start()

    ctx.telemetry.emit_system_event("STARTUP", {
        "version": "0.10",
        "pattern_pack_loaded": ctx.state.pattern_pack_loaded,
        "trade_locked": ctx.state.trade_locked,
    })
    
    yield
    
    # Shutdown
    print("[BULUT] Shutting down...")
    await ctx.scheduler.stop()
    if getattr(ctx, "_executor", None):
        await ctx.executor.cleanup()
    ctx.telemetry.emit_system_event("SHUTDOWN")


app = FastAPI(
    title="Tezaver Bulut",
    description="Cloud trading system for Tezaver",
    version="0.10",
    lifespan=lifespan,
)

# Include routers
app.include_router(health_router)
app.include_router(ranking_router)
app.include_router(trade_router)
app.include_router(bars_router)
app.include_router(daemon_router)
app.include_router(plans_router)
app.include_router(execution_router)
app.include_router(reconcile_router)
app.include_router(positions_router)
app.include_router(exit_profiles_router)
app.include_router(exchangeinfo_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "tezaver-bulut",
        "version": "0.01",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
