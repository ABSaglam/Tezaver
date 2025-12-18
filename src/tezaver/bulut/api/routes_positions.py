# Tezaver Bulut - Positions API
"""
Positions and Exit Profiles API.
"""

from fastapi import APIRouter
from tezaver.bulut.core.context import get_context

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("/open")
async def get_open_positions():
    """Get open positions."""
    ctx = get_context()
    positions = ctx.persistence.get_open_positions()
    return {"count": len(positions), "positions": positions}

@router.get("/exits/profiles")
async def list_exit_profiles():
    """List loaded exit profiles."""
    ctx = get_context()
    # Loader doesn't expose list method directly, need to add one?
    # Or access implementation detail.
    # Let's just return what's in private dict for now or add getter.
    # Accessing ._profiles
    profiles = [p.to_dict() for p in ctx.exit_profile_loader._profiles.values()]
    return {"count": len(profiles), "profiles": profiles}
