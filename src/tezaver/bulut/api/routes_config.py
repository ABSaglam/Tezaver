from fastapi import APIRouter
from tezaver.bulut.app_backend import get_context

router = APIRouter()

@router.post("/snapshot")
async def take_snapshot():
    """Manual config snapshot."""
    ctx = get_context()
    if not ctx: return {}
    return ctx.drift_guard.check_and_record(source="MANUAL")

@router.get("/snapshot/latest")
async def get_latest_snapshot():
    """Get latest snapshot info."""
    ctx = get_context()
    if not ctx: return {}
    return ctx.persistence.get_latest_config_snapshot()
