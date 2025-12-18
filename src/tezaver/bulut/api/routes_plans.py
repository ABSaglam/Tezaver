# Tezaver Bulut - Plan API Routes
"""
API endpoints for Trade Plans.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from tezaver.bulut.core.context import get_context


router = APIRouter(prefix="/plans", tags=["plans"])


class PlanAcceptRequest(BaseModel):
    idempotency_key: str


@router.get("/latest")
async def get_latest_plans(limit: int = 50):
    """Get latest trade plans."""
    ctx = get_context()
    plans = ctx.persistence.get_latest_plans(limit)
    return {
        "count": len(plans),
        "plans": plans
    }


@router.post("/accept")
async def accept_plan(req: PlanAcceptRequest):
    """
    Manually accept a PROPOSED plan.
    """
    ctx = get_context()
    
    # Update status in DB
    # We assume validation is done or we trust operator
    ctx.persistence.update_plan_status(req.idempotency_key, "ACCEPTED")
    
    # Emit event (MANUAL_ACCEPT)
    # Re-fetch plan to emit details? Or just minimal?
    # For now minimal
    ctx.telemetry.emit_trade_plan_accepted(
        {"idempotency_key": req.idempotency_key, "symbol": "UNKNOWN"}, 
        mode="MANUAL"
    )
    
    return {"status": "ok", "message": "Plan accepted"}
