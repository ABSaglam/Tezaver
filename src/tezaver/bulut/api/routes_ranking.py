# Tezaver Bulut - Ranking API Routes
"""
Ranking endpoints for Bulut API.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from tezaver.bulut.core.context import get_context
from tezaver.bulut.engine.scanner import run_scan


router = APIRouter(prefix="/ranking", tags=["ranking"])


# Cache latest ranking
_latest_ranking: Optional[dict] = None


@router.get("/latest")
async def get_latest_ranking():
    """
    Get latest ranking snapshot.
    
    Returns cached ranking or empty if no scan has run.
    """
    global _latest_ranking
    
    if _latest_ranking is None:
        return {
            "status": "no_data",
            "message": "No ranking available. Run a scan first.",
        }
    
    return {
        "status": "ok",
        "ranking": _latest_ranking,
    }


@router.post("/scan")
async def trigger_scan():
    """
    Manually trigger a scan cycle.
    
    Returns new ranking snapshot.
    """
    global _latest_ranking
    
    ctx = get_context()
    
    # Load pattern pack if available
    ctx.load_pattern_pack()
    
    # Run scan
    # Check hot-reload
    ctx.pattern_loader.check_reload()
    
    ranking = run_scan(
        config=ctx.config,
        pattern_loader=ctx.pattern_loader,
        universe=universe,
        bars_store=ctx.bars_store,
        stabilizer=ctx.ranking_stabilizer
    )
    
    # Cache and emit telemetry
    _latest_ranking = ranking.to_dict()
    
    # Add pack loaded status to telemetry
    meta = ctx.pattern_loader.get_pack_meta()
    _latest_ranking["pattern_pack"] = meta
    
    ctx.telemetry.emit_ranking_snapshot(_latest_ranking)
    ctx.state.last_scan_ts = ranking.cycle_ts
    
    return {
        "status": "ok",
        "ranking": _latest_ranking,
        "shortlist_count": len(ranking.shortlist),
        "pattern_pack_loaded": ctx.state.pattern_pack_loaded,
    }


@router.get("/shortlist")
async def get_shortlist():
    """
    Get only the shortlist (above threshold, top-k limited).
    """
    global _latest_ranking
    
    if _latest_ranking is None:
        return {
            "status": "no_data",
            "shortlist": [],
        }
    
    # Parse and get shortlist
    from tezaver.bulut.schemas.ranking_snapshot_v1 import RankingSnapshotV1
    ranking = RankingSnapshotV1.from_dict(_latest_ranking)
    
    if ranking is None:
        return {
            "status": "parse_error",
            "shortlist": [],
        }
    
    return {
        "status": "ok",
        "shortlist": [c.to_dict() for c in ranking.shortlist],
        "threshold": ranking.threshold,
        "topk": ranking.topk,
    }
