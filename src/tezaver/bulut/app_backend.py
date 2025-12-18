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
    
    # v0.13 Time Sync Init
    if ctx.config.time_sync_enabled:
        print("[BULUT] Initializing Time Sync...")
        await ctx.time_sync.refresh()
    
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
    
    # v0.20 Startup Self-Test
    if getattr(ctx.config, "startup_selftest_enabled", True):
        print("[BULUT] Running startup self-test (Env Doctor)...")
        report = ctx.env_doctor.run_checks(ctx)
        status = report.get("status", "OK")
        
        print(f"[BULUT] Env Status: {status}")
        if report.get("errors"):
            print(f"[BULUT] Errors: {report['errors']}")
            
        if status == "FAIL":
            print("[BULUT] CRITICAL: Startup Self-Test Failed!")
            
            # Alert
            ctx.persistence.insert_alert(
                "ERROR", "STARTUP_SELFTEST_FAIL", 
                "Environment checks failed. System unsafe.",
                {"errors": report["errors"]}
            )
            
            # Export Incident
            if getattr(ctx.config, "startup_export_incident_on_fail", True):
                try:
                    path = ctx.incident_bundle.create_bundle(ctx, "startup_selftest_fail")
                    print(f"[BULUT] Incident exported to: {path}")
                except Exception as e:
                    print(f"[BULUT] Failed to export incident: {e}")
            
            # Fail Fast or Degrade
            if getattr(ctx.config, "startup_fail_fast", True):
                print("[BULUT] Fail-Fast enabled. Aborting startup.")
                # We raise RuntimeError to stop uvicorn/fastapi startup
                raise RuntimeError(f"Startup Self-Test Failed: {report['errors']}")
            else:
                print("[BULUT] Fail-Fast disabled. Entering DEGRADED mode.")
                ctx.state.startup_degraded = True
                ctx.update_trade_lock() # Lock trading
    
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

from tezaver.bulut.api.routes_risk import router as risk_router
app.include_router(risk_router)

from tezaver.bulut.api.routes_time_sync import router as time_sync_router
app.include_router(time_sync_router)

from tezaver.bulut.api.routes_ops import router as ops_router
app.include_router(ops_router)

from tezaver.bulut.api.routes_income import router as income_router
app.include_router(income_router)

# v0.19 FX
from tezaver.bulut.api.routes_fx import router as fx_router
app.include_router(fx_router)

# v0.20 Env
from tezaver.bulut.api.routes_env import router as env_router
app.include_router(env_router)



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
