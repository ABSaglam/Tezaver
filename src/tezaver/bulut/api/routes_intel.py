# Tezaver Bulut - Intel API Routes
"""
API for Intel Contract management.
Exposes Registry Service functionality.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from tezaver.bulut.core.context import get_context

router = APIRouter(tags=["intel"])

class IntelPublishRequest(BaseModel):
    bundle_id: str

class IntelActivateRequest(BaseModel):
    bundle_id: str

@router.get("/active")
async def get_active_intel():
    """Get currently active intel pointer."""
    ctx = get_context()
    ptr = ctx.intel_registry.get_active()
    return {"active": ptr}

@router.get("/list")
async def list_intel(limit: int = 20):
    """List published and incoming intel."""
    ctx = get_context()
    published = ctx.intel_registry.list_published(limit)
    incoming = ctx.intel_registry.list_incoming()
    
    return {
        "published": published,
        "incoming": incoming
    }

@router.post("/publish")
async def publish_intel(req: IntelPublishRequest):
    """
    Publish an incoming bundle.
    Blocks if INTEL_CHANGE_BLOCKED_MAINNET_ARMED condition met.
    """
    ctx = get_context()
    try:
        ctx.intel_registry.publish(ctx, req.bundle_id)
        return {"status": "ok", "bundle_id": req.bundle_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/activate")
async def activate_intel(req: IntelActivateRequest):
    """
    Activate a published bundle.
    Blocks if INTEL_CHANGE_BLOCKED_MAINNET_ARMED condition met.
    """
    ctx = get_context()
    try:
        ctx.intel_registry.activate(ctx, req.bundle_id)
        return {"status": "ok", "active": req.bundle_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/rollback")
async def rollback_intel(req: IntelActivateRequest):
    """
    Rollback to previous bundle (explicit activation).
    Blocks if INTEL_CHANGE_BLOCKED_MAINNET_ARMED condition met.
    """
    ctx = get_context()
    try:
        # Reusing activate logic for manual rollback
        ctx.intel_registry.activate(ctx, req.bundle_id)
        return {"status": "ok", "active": req.bundle_id, "mode": "rollback"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
