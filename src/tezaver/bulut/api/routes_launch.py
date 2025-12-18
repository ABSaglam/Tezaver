from fastapi import APIRouter, Depends, Query
from tezaver.bulut.app_backend import get_context

router = APIRouter()

@router.get("/checklist")
async def get_launch_checklist():
    """Get last run checklist result or run if empty."""
    ctx = get_context()
    if not ctx: return {}
    
    cl = ctx.launch_checklist.get_last_result()
    if not cl:
        return ctx.launch_checklist.run_checks(ctx)
    return cl

@router.post("/checklist/run")
async def run_launch_checklist():
    """Force run checklist."""
    ctx = get_context()
    if not ctx: return {}
    return ctx.launch_checklist.run_checks(ctx)
