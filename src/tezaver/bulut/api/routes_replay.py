# Tezaver Bulut - Replay API Routes
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.core.replay_collector import ReplayCollectorService
from tezaver.bulut.core.replay_engine import ReplayEngine
from tezaver.bulut.schemas.replay_v1 import ReplayResultV1

router = APIRouter(prefix="/replay", tags=["Replay Lab"])

def get_context(request) -> BulutContext:
    return request.app.state.context

# --- Models ---
class CreateBundleRequest(BaseModel):
    notes: Optional[str] = ""

class RunReplayRequest(BaseModel):
    bundle_id: str

class ReplayBundleSummary(BaseModel):
    bundle_id: str
    cycle_ts: str
    created_ts: str
    notes: str
    status: Optional[str]

# --- Endpoints ---

@router.post("/bundle/create")
async def create_bundle(req: CreateBundleRequest, request: Request):
    ctx = request.app.state.context
    collector = ReplayCollectorService(ctx)
    try:
        # Snapshot CURRENT state
        bundle = collector.create_bundle_from_current_state(notes=req.notes)
        return {"bundle_id": bundle.bundle_id, "status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bundles/latest", response_model=List[ReplayBundleSummary])
async def list_bundles(request: Request, limit: int = 20):
    # We query DB directly via persistence
    ctx = request.app.state.context
    conn = ctx.persistence._get_conn()
    conn.row_factory = import_sqlite_row_factory()
    cur = conn.cursor()
    cur.execute("SELECT bundle_id, cycle_ts, created_ts, notes, status FROM replay_bundles ORDER BY created_ts DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    
    return [dict(r) for r in rows]

@router.post("/run")
async def run_replay(req: RunReplayRequest, request: Request):
    ctx = request.app.state.context
    collector = ReplayCollectorService(ctx)
    engine = ReplayEngine()
    
    # Load bundle
    bundle = collector.get_bundle(req.bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail="Bundle not found")
        
    try:
        result = engine.run_replay(bundle)
        
        # Save result to DB
        # Update replay_bundles table with result_json and status
        import json
        res_json = json.dumps({
            "run_id": result.run_id,
            "status": result.status,
            "drift_details": result.drift_details
        })
        
        conn = ctx.persistence._get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE replay_bundles SET result_json=?, status=? WHERE bundle_id=?", 
                   (res_json, result.status, bundle.bundle_id))
        conn.commit()
        conn.close()
        
        return {
            "run_id": result.run_id,
            "status": result.status,
            "drift_details": result.drift_details
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Replay Error: {e}")

@router.get("/result/{bundle_id}")
async def get_result(bundle_id: str, request: Request):
    # Fetch from DB
    ctx = request.app.state.context
    conn = ctx.persistence._get_conn()
    conn.row_factory = import_sqlite_row_factory()
    cur = conn.cursor()
    cur.execute("SELECT result_json FROM replay_bundles WHERE bundle_id=?", (bundle_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row or not row["result_json"]:
        return {"status": "none"}
        
    import json
    return json.loads(row["result_json"])

def import_sqlite_row_factory():
    import sqlite3
    return sqlite3.Row
