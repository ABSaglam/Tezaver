"""
Timeframe Utils - V4 Compatible Shim

Provides ETA calculation for closed bars.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple

def eta_to_next_close(timeframe: str) -> Optional[int]:
    """
    Calculate seconds until next bar close.
    Returns None if timeframe is unknown.
    """
    tf_minutes = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "1d": 1440,
    }
    
    minutes = tf_minutes.get(timeframe)
    if minutes is None:
        return None
        
    now = datetime.now()
    elapsed = (now.hour * 60 + now.minute) % minutes
    remaining = minutes - elapsed
    
    return remaining * 60 - now.second

def format_eta(seconds: Optional[int]) -> str:
    """Format seconds as mm:ss."""
    if seconds is None:
        return "N/A"
    if seconds < 0:
        return "00:00"
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"
