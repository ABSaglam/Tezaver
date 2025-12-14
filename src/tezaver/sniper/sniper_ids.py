"""
Sniper IDs - Standardized trade_id helpers
==========================================

Single source of truth for trade_id generation across Sniper Arena.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd


def to_iso(ts: Any) -> str:
    """
    Convert timestamp to ISO format string (YYYY-MM-DDTHH:MM:SS).
    
    Handles: None, str, pd.Timestamp, datetime.
    """
    if ts is None:
        return ""
    if isinstance(ts, str):
        # Assume already iso-ish, normalize space to T
        return ts.replace(" ", "T")[:19]
    if isinstance(ts, pd.Timestamp):
        ts = ts.to_pydatetime()
    if isinstance(ts, datetime):
        return ts.replace(microsecond=0).isoformat()
    return str(ts)[:19]


def make_trade_id(event_id: Any, entry_ts: Any) -> str:
    """
    Create unique trade_id from event_id and entry timestamp.
    
    Format: "{event_id}|{entry_ts_iso}"
    """
    return f"{event_id}|{to_iso(entry_ts)}"


def ensure_trade_id_column(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure DataFrame has a trade_id column.
    
    Adds column if missing using event_id + entry_ts/event_time.
    Returns the same DataFrame (modified in-place if needed).
    """
    if "trade_id" in df.columns:
        return df
    
    # Find timestamp column
    ts_col = None
    for c in ["entry_ts", "event_time", "ts"]:
        if c in df.columns:
            ts_col = c
            break
    
    # Find event id column
    id_col = None
    for c in ["event_id", "entry_id"]:
        if c in df.columns:
            id_col = c
            break
    
    if id_col is None or ts_col is None:
        # Can't create trade_id, return as-is
        return df
    
    df["trade_id"] = df.apply(
        lambda r: make_trade_id(r[id_col], r[ts_col]), 
        axis=1
    )
    return df
