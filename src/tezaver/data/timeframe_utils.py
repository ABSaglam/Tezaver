"""
Timeframe utilities for Tezaver Mac.
Standardizes timeframe strings across the application.
"""

from typing import List, Dict

SUPPORTED_TIMEFRAMES: List[str] = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]

CCXT_TIMEFRAME_MAP: Dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1w": "1w",
}

def is_supported_timeframe(tf: str) -> bool:
    """
    Checks if the given timeframe is supported.
    """
    return tf in SUPPORTED_TIMEFRAMES

def normalize_timeframe(tf: str) -> str:
    """
    Normalizes a timeframe string to the standard format.
    Currently assumes input is already close to standard or handles basic variations if needed.
    If not recognized, returns the input as is (or could raise ValueError).
    """
    # Basic normalization logic could go here.
    # For now, we assume inputs are clean or we just pass them through if they match keys.
    
    if tf in CCXT_TIMEFRAME_MAP:
        return CCXT_TIMEFRAME_MAP[tf]
    
    # Handle common variations if necessary, e.g. "1min" -> "1m"
    if tf == "1min":
        return "1m"
        
    return tf
