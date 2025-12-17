# Internal Account State from Telemetry
"""
Derives internal position state from NDJSON telemetry events.

Used by reconcile to compare internal vs exchange state.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class InternalPosition:
    """Internal position record."""
    symbol: str
    side: str  # "LONG" or "SHORT"
    qty: float
    avg_price: float
    opened_ts: str


def get_internal_positions_from_events(events_path: Path, tail_n: int = 2000) -> Dict[str, float]:
    """
    Parse internal positions from NDJSON telemetry events.
    
    Looks for:
    - PROOF_OPEN / ORDER_LIFECYCLE_DONE with action=OPEN -> opens position
    - PROOF_CLOSE / ORDER_LIFECYCLE_DONE with action=CLOSE -> closes position
    
    Returns:
        {symbol: qty} where qty is signed (positive=long, negative=short)
    """
    import json
    
    positions: Dict[str, float] = {}
    
    if not events_path.exists():
        return positions
    
    try:
        with open(events_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            tail_lines = lines[-tail_n:] if len(lines) > tail_n else lines
            
            for line in tail_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                et = e.get("event_type", "")
                symbol = e.get("symbol")
                
                if not symbol:
                    continue
                
                # PROOF_OPEN -> open position
                if et in ("PROOF_OPEN", "POSITION_OPENED"):
                    side = e.get("side", "LONG")
                    qty = abs(float(e.get("qty", 0) or e.get("quantity", 0) or e.get("position_qty", 0)))
                    if side.upper() in ("SELL", "SHORT"):
                        qty = -qty
                    positions[symbol] = qty
                
                # ORDER_LIFECYCLE_DONE with action=OPEN
                elif et == "ORDER_LIFECYCLE_DONE":
                    action = e.get("action", "")
                    if action == "OPEN":
                        side = e.get("side", "BUY")
                        qty = abs(float(e.get("filled_qty", 0) or e.get("qty", 0)))
                        if side.upper() in ("SELL", "SHORT"):
                            qty = -qty
                        positions[symbol] = qty
                    elif action == "CLOSE":
                        # Closing -> remove position
                        positions[symbol] = 0.0
                
                # PROOF_CLOSE / POSITION_CLOSED -> close position
                elif et in ("PROOF_CLOSE", "POSITION_CLOSED"):
                    positions[symbol] = 0.0
    
    except Exception:
        pass
    
    # Filter out zero positions
    return {s: q for s, q in positions.items() if abs(q) > 0.0001}


def get_internal_positions(events_path: Path = None) -> Optional[Dict[str, float]]:
    """
    Get internal positions for reconcile.
    
    Args:
        events_path: Path to NDJSON file (defaults to data/logs/live_events.ndjson)
    
    Returns:
        {symbol: qty} or None if data unavailable
    """
    if events_path is None:
        events_path = Path("data/logs/live_events.ndjson")
    
    if not events_path.exists():
        return None
    
    return get_internal_positions_from_events(events_path)


def get_internal_state_summary(events_path: Path = None) -> Dict[str, Any]:
    """
    Get summary for UI display.
    
    Returns:
        {
            "positions": {symbol: qty},
            "available": True/False,
            "position_count": int,
        }
    """
    positions = get_internal_positions(events_path)
    
    if positions is None:
        return {
            "positions": {},
            "available": False,
            "position_count": 0,
        }
    
    return {
        "positions": positions,
        "available": True,
        "position_count": len(positions),
    }
