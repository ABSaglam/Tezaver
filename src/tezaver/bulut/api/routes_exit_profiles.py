# Tezaver Bulut - Exit Profiles API
"""
API for managing exit profiles.
"""

from fastapi import APIRouter
from tezaver.bulut.core.context import get_context
from datetime import datetime

router = APIRouter(prefix="/exit_profiles", tags=["exit_profiles"])

@router.post("/bootstrap")
async def bootstrap_exit_profiles(force: bool = False):
    """
    Force bootstrap example exit profiles with backup and validation.
    Returns detailed statistics.
    """
    ctx = get_context()
    
    # Run Bootstrap
    result = ctx.exit_profile_loader.ensure_defaults(force=force)
    
    # Telemetry
    telemetry_data = {
        "ts": datetime.now().isoformat(),
        **result
    }
    ctx.telemetry.emit_exit_profiles_bootstrap(telemetry_data)
    
    # Reload if successful
    if result["ok"]:
        ctx.exit_profile_loader._load_profiles()
    
    return result
