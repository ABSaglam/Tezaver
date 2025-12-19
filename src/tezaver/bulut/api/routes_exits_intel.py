# Tezaver Bulut - Exit Intel API Routes (P8)
"""
REST endpoints for Exit Intelligence Engine.
"""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import Optional


router = APIRouter(prefix="/exits", tags=["exits"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


@router.get("/status")
async def get_exit_intel_status(request: Request):
    """Get exit intel engine status."""
    ctx = get_ctx(request)
    
    try:
        engine = ctx.exit_intel_engine
        return engine.get_status()
    except Exception as e:
        return {
            "profiles_loaded": 0,
            "profile_ids": [],
            "decisions_count": 0,
            "error": str(e)
        }


@router.get("/decisions/latest")
async def get_latest_decisions(request: Request, limit: int = 50):
    """Get latest exit decisions."""
    ctx = get_ctx(request)
    
    try:
        engine = ctx.exit_intel_engine
        return engine.get_decisions(limit=min(limit, 200))
    except Exception as e:
        return []


class ExitPreviewRequest(BaseModel):
    symbol: str
    entry_price: float
    side: str = "LONG"
    pattern_id: Optional[str] = None
    current_price: Optional[float] = None
    atr_value: Optional[float] = None


@router.post("/preview")
async def preview_exit_levels(request: Request, body: ExitPreviewRequest):
    """
    Preview exit levels for given parameters.
    
    Useful for UI preview without real position.
    """
    ctx = get_ctx(request)
    
    try:
        engine = ctx.exit_intel_engine
        return engine.preview_exit(
            symbol=body.symbol,
            entry_price=body.entry_price,
            side=body.side,
            pattern_id=body.pattern_id,
            current_price=body.current_price,
            atr_value=body.atr_value
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions/{symbol}/levels")
async def get_position_exit_levels(request: Request, symbol: str):
    """
    Get computed exit levels for an open position.
    """
    ctx = get_ctx(request)
    
    try:
        # Get position
        positions = ctx.persistence.get_positions(symbol=symbol, status="OPEN")
        if not positions:
            raise HTTPException(status_code=404, detail=f"No open position for {symbol}")
        
        position = positions[0]
        engine = ctx.exit_intel_engine
        
        # Get current price if available
        current_price = None
        try:
            current_price = ctx.bars_store.get_latest_price(symbol)
        except Exception:
            pass
        
        # Get ATR if available
        atr_value = None
        try:
            atr_value = ctx.bars_store.get_atr(symbol, "1h", 14)
        except Exception:
            pass
        
        levels = engine.compute_exit_levels(position, current_price, atr_value)
        
        return {
            "symbol": symbol,
            "position_id": position.get("position_id", ""),
            "entry_price": position.get("entry_price"),
            "sl_price": levels.sl_price,
            "tp_price": levels.tp_price,
            "trailing_active": levels.trailing_active,
            "trailing_sl": levels.trailing_sl,
            "break_even_triggered": levels.break_even_triggered,
            "time_stop_due": levels.time_stop_due,
            "profile_id": levels.profile_id,
            "rule_source": levels.rule_source
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
