"""
Tezaver Normalize Engine v1
============================

Converts entry_bar_offset to normalized_entry_ts with auto-snap functionality.

Key Features:
- Offset → Timestamp conversion
- Closed-bar lock (ensure bar is closed before event_time)
- Auto-snap to pivot highs within ±3 bars
- Snap metadata (reason, distance, confidence, version)
"""

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class NormalizeResult:
    """Result of entry normalization with snap metadata."""
    symbol: str
    timeframe: str
    event_time_iso: str
    entry_offset_in: int
    entry_offset_out: int
    entry_ts_iso: str
    snap_reason: str
    snap_distance_bars: int
    snap_confidence: float
    snap_algo_version: str
    
    def to_dict(self):
        return asdict(self)


def ensure_open_time(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure df has open_time column as datetime."""
    if 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'], errors='coerce')
    elif 'datetime' in df.columns:
        df['open_time'] = pd.to_datetime(df['datetime'], errors='coerce')
    elif 'timestamp' in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms', errors='coerce')
    elif 'ts' in df.columns:
        df['open_time'] = pd.to_datetime(df['ts'], unit='s', errors='coerce')
    else:
        raise ValueError("No time column found in history dataframe")
    
    return df


def load_history_for_normalize(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load history bars for normalization."""
    path = Path(f"coin_cells/{symbol}/data/history_{timeframe}.parquet")
    
    if not path.exists():
        raise FileNotFoundError(
            f"History file not found: {path}. "
            f"Ensure {symbol} has {timeframe} history data."
        )
    
    df = pd.read_parquet(path)
    
    if df.empty:
        raise ValueError(f"History dataframe is empty for {symbol} {timeframe}")
    
    df = ensure_open_time(df)
    df = df.sort_values('open_time').reset_index(drop=True)
    
    return df


def find_event_bar_index(df_history: pd.DataFrame, event_time: pd.Timestamp) -> int:
    """
    Find the bar index for event_time using closed-bar lock.
    
    Returns the last bar where open_time <= event_time.
    """
    mask = df_history['open_time'] <= event_time
    matching_indices = df_history[mask].index.tolist()
    
    if not matching_indices:
        # Event is before first bar
        return 0
    
    return matching_indices[-1]


def find_pivot_snap_offset(
    df_history: pd.DataFrame,
    base_idx: int,
    window_size: int = 3
) -> tuple[int, str, float]:
    """
    Find best snap offset within ±window_size bars of base_idx.
    
    Returns:
        (snap_offset_delta, reason, confidence)
    
    Logic:
        - Search window: [base_idx - window_size, base_idx + window_size]
        - Find bar with highest 'high' value (pivot high)
        - If different from base_idx, snap to it
    """
    start_idx = max(0, base_idx - window_size)
    end_idx = min(len(df_history) - 1, base_idx + window_size)
    
    # Extract window
    window = df_history.iloc[start_idx:end_idx+1].copy()
    
    if 'high' not in window.columns:
        # No high column, can't detect pivot
        return 0, "KEEP:no_high_column", 0.50
    
    # Find pivot high
    pivot_idx_in_window = window['high'].idxmax()
    pivot_idx_global = pivot_idx_in_window
    
    if pivot_idx_global == base_idx:
        # Base is already the pivot
        return 0, "KEEP:base_is_pivot", 0.55
    
    # Calculate snap
    snap_delta = pivot_idx_global - base_idx
    distance = abs(snap_delta)
    
    if distance > window_size:
        # Shouldn't happen due to clipping, but defensive
        return 0, "KEEP:pivot_too_far", 0.50
    
    reason = f"SNAP:pivot_high_window"
    confidence = 0.70 if distance <= window_size else 0.60
    
    return snap_delta, reason, confidence


def normalize_entry(
    symbol: str,
    timeframe: str,
    event_time: pd.Timestamp,
    entry_bar_offset: int
) -> NormalizeResult:
    """
    Normalize entry_bar_offset to timestamp with auto-snap.
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe (15m, 1h, 4h)
        event_time: Event timestamp
        entry_bar_offset: Bar offset from event (positive = forward)
    
    Returns:
        NormalizeResult with normalized timestamp and snap metadata
    """
    # Load history
    df_history = load_history_for_normalize(symbol, timeframe)
    
    # Find event bar index
    event_idx = find_event_bar_index(df_history, event_time)
    
    # Calculate base index for entry
    base_idx = event_idx + entry_bar_offset
    
    # Clip to valid range
    was_clipped = False
    if base_idx < 0:
        base_idx = 0
        was_clipped = True
    elif base_idx >= len(df_history):
        base_idx = len(df_history) - 1
        was_clipped = True
    
    # Apply pivot snap
    snap_delta, snap_reason, snap_confidence = find_pivot_snap_offset(
        df_history, base_idx, window_size=3
    )
    
    # Calculate final output offset and index
    out_idx = base_idx + snap_delta
    
    # Clip output index
    if out_idx < 0:
        out_idx = 0
    elif out_idx >= len(df_history):
        out_idx = len(df_history) - 1
    
    # Calculate output offset (relative to event_idx)
    entry_offset_out = out_idx - event_idx
    
    # Get timestamp
    entry_ts = df_history.iloc[out_idx]['open_time']
    entry_ts_iso = entry_ts.isoformat()
    
    # Adjust reason if clipped
    if was_clipped:
        snap_reason = f"CLIP:{snap_reason}"
    
    # Calculate snap distance
    snap_distance_bars = abs(entry_offset_out - entry_bar_offset)
    
    return NormalizeResult(
        symbol=symbol,
        timeframe=timeframe,
        event_time_iso=event_time.isoformat(),
        entry_offset_in=entry_bar_offset,
        entry_offset_out=entry_offset_out,
        entry_ts_iso=entry_ts_iso,
        snap_reason=snap_reason,
        snap_distance_bars=snap_distance_bars,
        snap_confidence=snap_confidence,
        snap_algo_version="normalize_entry_v1"
    )


def normalize_entry_from_df(
    df_history: pd.DataFrame,
    symbol: str,
    timeframe: str,
    event_time: pd.Timestamp,
    entry_bar_offset: int
) -> NormalizeResult:
    """
    Test-friendly version that accepts pre-loaded df_history.
    
    Same logic as normalize_entry() but doesn't load from file.
    """
    # Ensure df has correct format
    df_history = ensure_open_time(df_history)
    df_history = df_history.sort_values('open_time').reset_index(drop=True)
    
    # Find event bar index
    event_idx = find_event_bar_index(df_history, event_time)
    
    # Calculate base index
    base_idx = event_idx + entry_bar_offset
    
    # Clip
    was_clipped = False
    if base_idx < 0:
        base_idx = 0
        was_clipped = True
    elif base_idx >= len(df_history):
        base_idx = len(df_history) - 1
        was_clipped = True
    
    # Pivot snap
    snap_delta, snap_reason, snap_confidence = find_pivot_snap_offset(
        df_history, base_idx, window_size=3
    )
    
    # Final output
    out_idx = base_idx + snap_delta
    
    # Clip output
    if out_idx < 0:
        out_idx = 0
    elif out_idx >= len(df_history):
        out_idx = len(df_history) - 1
    
    entry_offset_out = out_idx - event_idx
    entry_ts = df_history.iloc[out_idx]['open_time']
    entry_ts_iso = entry_ts.isoformat()
    
    if was_clipped:
        snap_reason = f"CLIP:{snap_reason}"
    
    snap_distance_bars = abs(entry_offset_out - entry_bar_offset)
    
    return NormalizeResult(
        symbol=symbol,
        timeframe=timeframe,
        event_time_iso=event_time.isoformat(),
        entry_offset_in=entry_bar_offset,
        entry_offset_out=entry_offset_out,
        entry_ts_iso=entry_ts_iso,
        snap_reason=snap_reason,
        snap_distance_bars=snap_distance_bars,
        snap_confidence=snap_confidence,
        snap_algo_version="normalize_entry_v1"
    )
