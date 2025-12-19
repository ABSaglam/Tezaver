# Tezaver Bulut - Dry Run API Routes (P4)
from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from tezaver.bulut.core.context import BulutContext

router = APIRouter(prefix="/dry_run", tags=["Dry Run"])

def get_ctx(request: Request) -> BulutContext:
    if not hasattr(request.app.state, "context"):
        raise HTTPException(status_code=500, detail="Context not initialized")
    return request.app.state.context

class StartRunRequest(BaseModel):
    cycles: int = 20

@router.post("/start")
async def start_dry_run(req: StartRunRequest, request: Request):
    ctx = get_ctx(request)
    try:
        run_id = await ctx.dry_run_service.start_run(req.cycles)
        return {"status": "STARTED", "run_id": run_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def get_dry_run_status(request: Request):
    ctx = get_ctx(request)
    return ctx.dry_run_service.get_status()

@router.get("/runs/latest")
async def get_latest_runs(request: Request, limit: int = 10):
    ctx = get_ctx(request)
    return ctx.persistence.get_latest_dry_runs(limit)
