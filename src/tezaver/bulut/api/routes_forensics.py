from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Dict, Optional
from tezaver.bulut.core.context import get_context

router = APIRouter()

@router.get("/timelines")
async def get_timelines(limit: int = 20):
    """
    Get latest cycle forensic timelines.
    """
    ctx = get_context()
    if not ctx.persistence:
         raise HTTPException(status_code=503, detail="Persistence not available")
         
    return ctx.persistence.get_latest_timelines(limit=limit)
