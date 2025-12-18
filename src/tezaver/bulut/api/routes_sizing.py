# Tezaver Bulut - Entry Sizing API Routes
"""
API endpoints for managing Entry Sizing Profiles.
Provides list, CRUD, and bootstrap capabilities.
Enforces Mainnet safety rules.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import List, Dict, Optional, Any
from pydantic import BaseModel

from tezaver.bulut.core.context import get_context, BulutContext
from tezaver.bulut.schemas.entry_sizing_profile_v1 import EntrySizingProfileV1

router = APIRouter(tags=["Entry Sizing"])

class ProfileResponse(BaseModel):
    profile_id: str
    priority: int
    rule_type: str
    scope: Dict
    safety: Dict

def check_mainnet_safety(ctx: BulutContext):
    """Block writes if ARMED on MAINNET unless override disabled."""
    # Check config override defaults to True
    block_armed = getattr(ctx.config, "entry_sizing_edit_block_on_mainnet_armed", True)
    if not block_armed:
        return

    is_mainnet = (ctx.config.mode == "REAL_MAINNET")
    is_armed = ctx.state.execution_armed
    
    if is_mainnet and is_armed:
        raise HTTPException(status_code=409, detail="SIZING_EDIT_BLOCKED_MAINNET_ARMED")

@router.get("/entry_sizing/profiles")
def list_profiles(ctx: BulutContext = Depends(get_context)) -> List[Dict]:
    """List all profiles."""
    profiles = ctx.entry_sizing_loader.load_all()
    # Return full dicts? Or concise list? Return full dicts for UI simplicity
    return [p.to_dict() for p in profiles]

@router.get("/entry_sizing/profile")
def get_profile(profile_id: str, ctx: BulutContext = Depends(get_context)) -> Dict:
    """Get single profile."""
    p = ctx.entry_sizing_loader.get_by_id(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found")
    return p.to_dict()

@router.post("/entry_sizing/validate")
def validate_profile(data: Dict = Body(...)):
    """Validate profile schema."""
    p = EntrySizingProfileV1.from_dict(data)
    if not p:
        raise HTTPException(status_code=400, detail="Invalid Entry Sizing Profile Schema")
    return {"status": "valid", "profile_id": p.profile_id}

@router.post("/entry_sizing/apply")
def apply_profile(data: Dict = Body(...), ctx: BulutContext = Depends(get_context)):
    """
    Save profile.
    Blocks if Mainnet+Armed.
    """
    check_mainnet_safety(ctx)
    
    p = EntrySizingProfileV1.from_dict(data)
    if not p:
         raise HTTPException(status_code=400, detail="Invalid Profile")
         
    # Save to disk
    import json
    path = ctx.entry_sizing_loader._profiles_dir / f"{p.profile_id}.json"
    
    # Backup if exists? Recommended for safety
    if path.exists():
        import shutil
        import time
        params_dir = path.parent
        backup_dir = params_dir / ".backups"
        backup_dir.mkdir(exist_ok=True)
        ts = int(time.time())
        shutil.copy2(path, backup_dir / f"{p.profile_id}.{ts}.bak")

    with open(path, "w") as f:
        json.dump(p.to_dict(), f, indent=2)
        
    # Force reload
    ctx.entry_sizing_loader.load_all(force=True)
    
    ctx.telemetry.emit("SIZING_PROFILE_UPDATED", {"profile_id": p.profile_id})
    return {"status": "saved", "path": str(path)}

@router.post("/entry_sizing/bootstrap")
def bootstrap_examples(force: bool = False, ctx: BulutContext = Depends(get_context)):
    """
    Bootstrap example profiles.
    """
    check_mainnet_safety(ctx)
    
    # Define examples
    examples = []
    
    # 1. Global Default
    from tezaver.bulut.schemas.entry_sizing_profile_v1 import (
        EntrySizingProfileV1, 
        EntrySizingRuleV1, 
        EntrySizingScopeV1,
        EntrySizingSafetyV1
    )
    
    ex1 = EntrySizingProfileV1(
        profile_id="global_default",
        version="1.0",
        priority=0,
        scope=EntrySizingScopeV1(symbol=None, pattern_id=None), # Global
        rule=EntrySizingRuleV1(
            type="fixed_notional",
            fixed_notional_usdt=20.0,
            leverage=1
        ),
        safety=EntrySizingSafetyV1(min_notional_usdt=5.0, max_notional_usdt=500.0)
    )
    examples.append(ex1)
    
    # 2. BTC Special
    ex2 = EntrySizingProfileV1(
        profile_id="btc_special",
        version="1.0",
        priority=100,
        scope=EntrySizingScopeV1(symbol="BTCUSDT"),
        rule=EntrySizingRuleV1(
            type="pct_of_cap",
            pct=50.0, # 50% of cell cap
            cap_ref="MAX_CELL_NOTIONAL",
            leverage=2
        ),
        safety=EntrySizingSafetyV1(min_notional_usdt=10.0)
    )
    examples.append(ex2)
    
    created = []
    for ex in examples:
        path = ctx.entry_sizing_loader._profiles_dir / f"{ex.profile_id}.json"
        if not path.exists() or force:
            with open(path, "w") as f:
                import json
                json.dump(ex.to_dict(), f, indent=2)
            created.append(ex.profile_id)
            
    ctx.entry_sizing_loader.load_all(force=True)
    return {"status": "bootstrapped", "created": created}
