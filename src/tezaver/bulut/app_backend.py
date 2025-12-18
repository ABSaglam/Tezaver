# Tezaver Bulut - FastAPI Backend
"""
Main FastAPI application for Tezaver Bulut.

Run with:
    uvicorn tezaver.bulut.app_backend:app --reload --port 8000
"""

from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from tezaver.bulut.core.context import bootstrap_context
from tezaver.bulut.core.context import bootstrap_context
# Import routers explicitly to avoid __init__ issues
from tezaver.bulut.api import routes_health
from tezaver.bulut.api import routes_ranking
from tezaver.bulut.api import routes_trade
from tezaver.bulut.api import routes_bars
from tezaver.bulut.api import routes_daemon
from tezaver.bulut.api import routes_plans
from tezaver.bulut.api import routes_execution
from tezaver.bulut.api import routes_reconcile
from tezaver.bulut.api import routes_positions
from tezaver.bulut.api import routes_exit_profiles
from tezaver.bulut.api import routes_exchangeinfo
from tezaver.bulut.api import routes_time_sync
from tezaver.bulut.api import routes_ops
from tezaver.bulut.api import routes_income
from tezaver.bulut.api import routes_fx
from tezaver.bulut.api import routes_env
from tezaver.bulut.api import routes_launch
from tezaver.bulut.api import routes_config
from tezaver.bulut.api import routes_migrations
from tezaver.bulut.api import routes_ui
from tezaver.bulut.api import routes_forensics
from tezaver.bulut.api import routes_intel
# from tezaver.bulut.api import routes_status # Might be missing?
# from tezaver.bulut.api import routes_logs # Might be missing?
# from tezaver.bulut.api import routes_control # Might be missing?
# from tezaver.bulut.api import routes_validation # Might be missing?
# from tezaver.bulut.api import routes_market # Might be missing?
# from tezaver.bulut.api import routes_reports # Assuming exists
from tezaver.bulut.api import routes_sizing
from tezaver.bulut.api import routes_proof_ladder


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
    
    # v0.23 Task Supervisor Setup
    # Register tasks
    
    # 1. Daemon (Scheduler)
    # Scheduler needs to support being run as a task.
    # We pass a lambda/partial to run_forever(ctx)
    ctx.task_supervisor.register("daemon", lambda: ctx.scheduler.run_forever(ctx))
    
    # 2. User Data Stream
    if ctx.config.user_data_ws_enabled:
        ctx.task_supervisor.register("user_data", lambda: ctx.user_data_stream.run_forever(ctx))

    # 3. Proof Ladder Auto Evaluate (v1)
    if ctx.config.proof_ladder_auto_evaluate_enabled:
        async def _proof_ladder_loop(app_ctx: BulutContext):
            while True:
                try:
                    # Evaluate
                    res = app_ctx.proof_ladder.evaluate()
                    if not res.passed:
                        # Log or Alert if critical failures found during auto-eval?
                        # Usually silent unless state degrades.
                        pass
                    
                    # Auto Advance?
                    if app_ctx.config.proof_ladder_auto_advance_enabled:
                        ok, msg = app_ctx.proof_ladder.advance_stage()
                        if ok:
                            print(f"[ProofLadder] Auto-Advanced: {msg}")
                            
                    await asyncio.sleep(app_ctx.config.proof_ladder_auto_evaluate_seconds)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    print(f"[ProofLadder] Auto-Eval Error: {e}")
                    await asyncio.sleep(60) # Backoff
        
        ctx.task_supervisor.register("proof_ladder", lambda: _proof_ladder_loop(ctx))

    # v0.26 Migrations (First thing logic)
    if ctx.config.migrations_enabled:
        dry = ctx.config.migrations_dry_run_on_start
        try:
            report = ctx.migration_runner.run_pending(dry_run=dry)
            if dry and report["plan"]:
                print(f"[Migrations] Dry Run Plan: {report['plan']}")
            elif report["executed"]:
                print(f"[Migrations] Executed {len(report['executed'])} migrations.")
        except Exception as e:
            if ctx.config.migrations_fail_fast:
                print(f"[Migrations] CRITICAL FAILURE: {e}")
                # We can't easily exit here without crashing uvicorn, but we can try
                raise e

    # v0.28 Constitution Check (Startup)
    ctx.constitution_guard.check_and_alert()

    # Start all via Supervisor
    await ctx.task_supervisor.start_all()

    # v0.29 Determinism Bridge Recovery (Startup)
    print("[BULUT] Running Determinism Recovery...")
    await ctx.executor.recover_executing_plans(ctx)
    ctx.policy.repair_state_drift(ctx)

    # v0.25 Config Drift Check (Startup)
    ctx.drift_guard.check_and_record(source="STARTUP")

    yield
    
    # Shutdown
    print("[BULUT] Shutting down...")
    
    # Stop Supervisor (stops all tasks)
    await ctx.task_supervisor.stop_all()
    
    # Cleanup components
    # ctx.scheduler.stop() handled by supervisor stop?
    # run_forever logic has finally: running=False.
    # explicit stop() call might be redundant but safe?
    # Supervisor cancels tasks.
    
    if getattr(ctx, "_executor", None):
        await ctx.executor.cleanup()
    ctx.telemetry.emit_system_event("SHUTDOWN")


app = FastAPI(
    title="Tezaver Bulut",
    description="Cloud trading system for Tezaver",
    version="0.10",
    lifespan=lifespan,
)

# v0.32 Ops Auth Middleware
from tezaver.bulut.core.config import get_config
from tezaver.bulut.core.ops_auth import check_ops_auth
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

@app.middleware("http")
async def ops_auth_middleware(request: Request, call_next):
    # Skip health check path? Maybe useful for k8s probes.
    if request.url.path.startswith("/health") or request.url.path.startswith("/docs") or request.url.path.startswith("/openapi.json"):
        return await call_next(request)
        
    cfg = get_config()
    try:
        await check_ops_auth(request, cfg)
    except Exception as e:
        # Re-raise HTTPException properly to return JSON error
        # Middleware catching simple exceptions works, but HTTPException needs specific handling
        # OR we just let it bubble if Starlette handles it?
        # Starlette handles HTTPException by returning response. But in middleware it's tricky.
        # Better: return JSONResponse if check fails.
        from fastapi.responses import JSONResponse
        if hasattr(e, "status_code"):
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        raise e
        
    response = await call_next(request)
    return response

# Include routers
# Note: Routers define their own prefix usually, but here we enforce it or double it?
# routes_health defines prefix="/health". app.include... prefix="/health" => /health/health.
# Removing prefix here to fix 404.
app.include_router(routes_health.router, tags=["Health"])
app.include_router(routes_ranking.router, prefix="/ranking", tags=["Ranking"])
app.include_router(routes_trade.router, prefix="/trade", tags=["Trade"])
app.include_router(routes_bars.router, prefix="/bars", tags=["Bars"])
app.include_router(routes_daemon.router, prefix="/daemon", tags=["Daemon"])
app.include_router(routes_reconcile.router, prefix="/reconcile", tags=["Reconcile"])
app.include_router(routes_positions.router, prefix="/positions", tags=["Positions"])
app.include_router(routes_exit_profiles.router, prefix="/exit-profiles", tags=["Exit Profiles"])
app.include_router(routes_exchangeinfo.router, prefix="/exchangeinfo", tags=["Exchange Info"])
app.include_router(routes_time_sync.router, prefix="/time-sync", tags=["Time Sync"])
app.include_router(routes_ops.router, prefix="/ops", tags=["Ops"])
app.include_router(routes_income.router, prefix="/income", tags=["Income"])
app.include_router(routes_fx.router, prefix="/fx", tags=["FX"])
app.include_router(routes_env.router, prefix="/env", tags=["Environment"])
app.include_router(routes_launch.router, prefix="/launch", tags=["Launch"])
app.include_router(routes_plans.router, prefix="/plans", tags=["Plans"])
app.include_router(routes_config.router, prefix="/config", tags=["Config"])
app.include_router(routes_migrations.router, prefix="/migrations", tags=["Migrations"])
app.include_router(routes_forensics.router, prefix="/cycles", tags=["Forensics"])
app.include_router(routes_intel.router, prefix="/intel", tags=["Intel"])
app.include_router(routes_ui.router, prefix="/ui", tags=["UI"])
app.include_router(routes_proof_ladder.router, prefix="/mainnet/ladder", tags=["Proof Ladder"])


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
