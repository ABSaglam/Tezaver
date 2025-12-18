# Tezaver Bulut - Reconcile API Routes
"""
Reconciliation API.
"""

from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/reconcile", tags=["reconcile"])

@router.post("/run")
async def run_reconcile():
    """Manually run reconciliation."""
    ctx = get_context()
    try:
        report = await ctx.reconciliation_service.reconcile()
        return {"status": "success", "report": report}
    except Exception as e:
        return {"status": "error", "message": str(e)}
