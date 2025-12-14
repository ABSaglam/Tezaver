# Timeframe Utilities
"""
Helpers for timeframe calculations.
"""

from datetime import datetime, timezone, timedelta
import math


def parse_timeframe_seconds(tf: str) -> int:
    """
    Parse timeframe string to seconds.
    
    Args:
        tf: Timeframe string (1m, 15m, 1h, 4h)
        
    Returns:
        Seconds in that timeframe
    """
    tf_map = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "1d": 86400,
    }
    
    if tf in tf_map:
        return tf_map[tf]
    
    # Try to parse dynamically
    if tf.endswith("m"):
        return int(tf[:-1]) * 60
    elif tf.endswith("h"):
        return int(tf[:-1]) * 3600
    elif tf.endswith("d"):
        return int(tf[:-1]) * 86400
    
    raise ValueError(f"Unsupported timeframe: {tf}")


def next_close_ts_utc(now_utc: datetime, tf: str) -> datetime:
    """
    Calculate next bar close timestamp.
    
    Args:
        now_utc: Current UTC time
        tf: Timeframe string
        
    Returns:
        Next bar close as UTC datetime
    """
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=timezone.utc)
    
    period_sec = parse_timeframe_seconds(tf)
    epoch = now_utc.timestamp()
    
    # Ceil to next period boundary
    next_epoch = math.ceil(epoch / period_sec) * period_sec
    
    return datetime.fromtimestamp(next_epoch, tz=timezone.utc)


def eta_to_next_close(now_utc: datetime, tf: str) -> tuple:
    """
    Calculate ETA to next bar close.
    
    Args:
        now_utc: Current UTC time
        tf: Timeframe string
        
    Returns:
        (eta_seconds, progress 0.0-1.0, next_close_dt)
    """
    next_close = next_close_ts_utc(now_utc, tf)
    period_sec = parse_timeframe_seconds(tf)
    
    eta_sec = max(0, (next_close - now_utc).total_seconds())
    progress = max(0.0, min(1.0, 1.0 - (eta_sec / period_sec)))
    
    return eta_sec, progress, next_close


def format_eta(eta_seconds: float) -> str:
    """Format ETA as mm:ss or hh:mm:ss."""
    eta_int = int(eta_seconds)
    
    if eta_int >= 3600:
        hours = eta_int // 3600
        mins = (eta_int % 3600) // 60
        secs = eta_int % 60
        return f"{hours}:{mins:02d}:{secs:02d}"
    else:
        mins = eta_int // 60
        secs = eta_int % 60
        return f"{mins}:{secs:02d}"
