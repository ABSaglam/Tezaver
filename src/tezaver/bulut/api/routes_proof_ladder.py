# Tezaver Bulut - Proof Ladder API
"""
API endpoints for Mainnet Proof Ladder.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any

from tezaver.bulut.core.context import get_context, BulutContext

router = APIRouter()

def _get_ctx():
    return get_context()

@router.get("/status")
def get_proof_ladder_status(ctx: BulutContext = Depends(_get_ctx)) -> Dict[str, Any]:
    """Get current Proof Ladder status."""
    state = ctx.persistence.get_proof_ladder_state()
    if not state:
        # If not seeded yet, try evaluating or seeding?
        # Just return empty or pending status
         return {
             "status": "NOT_SEEDED",
             "stage_id": None,
             "cap_usdt": 0.0,
             "effective_cap_usdt": ctx.proof_ladder.compute_effective_mainnet_cap(),
             "config_enabled": ctx.config.proof_ladder_enabled
         }
         
    # Parse last result
    import json
    last_res = {}
    try:
        if state["last_result_json"]:
            last_res = json.loads(state["last_result_json"])
    except: pass

    stage = ctx.proof_ladder.get_stage(state["stage_id"])
    next_stage_id = stage.next if stage else None

    return {
        "status": "ACTIVE",
        "stage_id": state["stage_id"],
        "cap_usdt": state["cap_usdt"],
        "effective_cap_usdt": ctx.proof_ladder.compute_effective_mainnet_cap(),
        "clean_hours": state["clean_hours"],
        "last_evaluated": state["last_evaluated_ts"],
        "last_result": last_res,
        "next_stage": next_stage_id,
        "config_enabled": ctx.config.proof_ladder_enabled
    }

@router.post("/evaluate")
def evaluate_proof_ladder(ctx: BulutContext = Depends(_get_ctx)) -> Dict[str, Any]:
    """Trigger manual evaluation."""
    res = ctx.proof_ladder.evaluate()
    return {
        "passed": res.passed,
        "stage_id": res.stage_id,
        "clean_hours": res.clean_hours,
        "reasons": res.reasons,
        "details": res.details
    }

@router.post("/advance")
def advance_stage(force: bool = False, ctx: BulutContext = Depends(_get_ctx)) -> Dict[str, Any]:
    """Advance to next stage if eligible."""
    ok, msg = ctx.proof_ladder.advance_stage(force=force)
    if not ok:
        # Check if blocked by ARMED mainnet
        if "ARMED" in msg:
             raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    
    return {"message": msg, "success": True}

@router.post("/bootstrap")
def bootstrap_proof_ladder(force: bool = False, ctx: BulutContext = Depends(_get_ctx)):
    """Bootstrap resources (if missing)."""
    # For now just ensure JSON exists?
    # Resource creation handled by `evaluate` seeding logic for state.
    # This endpoint could reset state if force=True.
    
    if force:
         # Reset state logic?
         # ctx.persistence.reset_proof_ladder() # Not implemented
         return {"message": "Force reset not implemented via API yet.", "success": False}
         
    # Trigger eval to seed
    ctx.proof_ladder.evaluate()
    return {"message": "Bootstrapped (Seeded via Eval)", "success": True}
