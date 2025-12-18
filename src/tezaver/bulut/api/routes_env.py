# Tezaver Bulut - Env Doctor Routes
from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/env", tags=["Environment"])

@router.get("/report")
async def get_env_report():
    """Get latest environment status report."""
    ctx = get_context()
    # Run fresh check or cache? "Run Now" implies fresh.
    # The requirement says "son env doctor report" but also "Run Now" button.
    # Let's run fresh for /report call, it's cheap enough usually.
    return ctx.env_doctor.run_checks(ctx)

@router.post("/run")
async def run_env_checks():
    """Run environment checks manually."""
    ctx = get_context()
    return ctx.env_doctor.run_checks(ctx)
