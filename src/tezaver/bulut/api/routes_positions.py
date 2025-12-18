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
    # Accessing ._profiles
    profiles = [p.to_dict() for p in ctx.exit_profile_loader._profiles.values()]
    return {"count": len(profiles), "profiles": profiles}

@router.post("/exits/bootstrap")
async def bootstrap_exit_profiles(force: bool = False):
    """
    Force bootstrap example exit profiles.
    """
    ctx = get_context()
    try:
        ctx.exit_profile_loader.ensure_defaults(force=force)
        # Force reload to pick up changes immediately
        ctx.exit_profile_loader._load_profiles()
        return {"status": "bootstrapped", "force": force}
    except Exception as e:
        return {"status": "error", "message": str(e)}
