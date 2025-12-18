# Tezaver Bulut - Bars API Routes
"""
Bars endpoint for testing ingestion.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime

from tezaver.bulut.core.context import get_context
from tezaver.bulut.schemas.bar_v1 import BarV1


router = APIRouter(prefix="/bars", tags=["bars"])


class BarIngestRequest(BaseModel):
    symbol: str
    tf: str
    open_ts: str
    close_ts: str
    o: float
    h: float
    l: float
    c: float
    v: float
    is_closed: bool = True


@router.post("/ingest")
async def ingest_bar(req: BarIngestRequest):
    """Ingest a bar for testing."""
    ctx = get_context()
    
    # Convert pydantic to BarV1
    try:
        bar = BarV1(
            symbol=req.symbol,
            tf=req.tf,
            open_ts=datetime.fromisoformat(req.open_ts.replace("Z", "+00:00")),
            close_ts=datetime.fromisoformat(req.close_ts.replace("Z", "+00:00")),
            o=req.o,
            h=req.h,
            l=req.l,
            c=req.c,
            v=req.v,
            is_closed=req.is_closed
        )
        ctx.bars_store.ingest_bar(bar)
        
        return {"status": "ok", "message": f"Ingested {req.symbol} {req.tf}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def get_bars_status():
    """Get bars store status."""
    ctx = get_context()
    return {
        "status": "ok",
        "store": ctx.bars_store.get_status()
    }
