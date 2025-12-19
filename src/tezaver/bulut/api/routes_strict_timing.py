# Tezaver Bulut - Strict Timing API
"""
API endpoints for Strict Timing Contract (P3).
"""
from fastapi import APIRouter, Depends, Request
from typing import Dict, Any, List

from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence

# NOTE: app_backend.py will attach context to app.state.context
router = APIRouter(prefix="/strict_timing", tags=["Strict Timing"])

def get_context(request: Request) -> BulutContext:
    return request.app.state.context

@router.get("/status")
def get_status(ctx: BulutContext = Depends(get_context)) -> Dict[str, Any]:
    """Get current strict timing status."""
    # We don't track detailed history in strict_timing service memory.
    # We query DB for last runs.
    
    # Needs persistence query for cycle_dedupe
    # But cycle_dedupe only stores SUCCESS.
    
    # Query logic inline for now or add to persistence?
    # Let's verify via persistence query manually.
    
    db: SqlitePersistence = ctx.persistence
    
    # Get last 24h stats roughly
    # We need a proper query method in persistence for stats. 
    # For now, return basic config and last run.
    
    # Get last run from cycle_dedupe (ordered by bar_close_ts DESC)
    # We didn't add an index or sort mechanism to table except PK.
    # PK is text ISO. Alphabetical sort works for ISO timestamps.
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM cycle_dedupe ORDER BY bar_close_ts DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    
    last_run = None
    if row:
        last_run = {
            "bar_close_ts": row[0],
            "last_cycle_id": row[1],
            "ran_at_ms": row[2],
            "run_ts": row[3]
        }
        
    return {
        "enabled": ctx.config.strict_timing_enabled,
        "max_drift_ms": ctx.config.max_drift_ms,
        "last_run": last_run,
        "mode": ctx.config.mode
    }

@router.get("/timeline")
def get_timeline(limit: int = 50, ctx: BulutContext = Depends(get_context)) -> List[Dict]:
    """Get cycle timelines enriched with strict timing."""
    # This queries `cycle_timelines` table (which stores JSON).
    # Persistence needs `get_recent_timelines`.
    # Let's check if that exists or we add raw query here.
    
    db: SqlitePersistence = ctx.persistence
    # Check if `get_recent_timelines` exists? 
    # I didn't see it in the snippet. I'll add query here to be safe.
    
    conn = db._get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT cycle_idx, cycle_ts, timeline_json FROM cycle_timelines ORDER BY cycle_idx DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    
    timelines = []
    import json
    for r in rows:
        try:
            t = json.loads(r[2])
            timelines.append(t)
        except:
            pass
            
    return timelines
