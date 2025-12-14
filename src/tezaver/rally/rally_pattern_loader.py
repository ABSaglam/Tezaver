"""
Rally Pattern Loader - Helpers for loading pattern datasets.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

import pandas as pd


def load_rally_patterns(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Load rally pattern dataset for any timeframe.
    
    Path: data/ai_datasets/{symbol}/{timeframe}/rally_patterns_v1.parquet
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m", "1h", "4h").
        
    Returns:
        DataFrame with rally patterns.
        
    Raises:
        FileNotFoundError: If pattern file doesn't exist.
    """
    symbol = symbol.upper()
    path = (
        Path("data/ai_datasets")
        / symbol
        / timeframe
        / "rally_patterns_v1.parquet"
    )
    if not path.exists():
        raise FileNotFoundError(
            f"Rally pattern dataset not found for {symbol} {timeframe} at {path}"
        )
    
    df = pd.read_parquet(path)
    return df


def load_silver_15m_patterns(symbol: str) -> pd.DataFrame:
    """
    Load Silver 15m pattern dataset.
    
    Default path: data/ai_datasets/{symbol}/15m/rally_patterns_v1.parquet
    Silver filtering: returns rows where is_silver == 1 or label_is_silver == 1.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        
    Returns:
        DataFrame with Silver patterns.
        
    Raises:
        FileNotFoundError: If pattern file doesn't exist.
        ValueError: If no silver label column found.
    """
    symbol = symbol.upper()
    path = (
        Path("data/ai_datasets")
        / symbol
        / "15m"
        / "rally_patterns_v1.parquet"
    )
    if not path.exists():
        raise FileNotFoundError(
            f"Silver 15m pattern dataset not found for {symbol} at {path}"
        )
    
    df = pd.read_parquet(path)
    
    # Find silver label column
    silver_col_candidates = ["is_silver", "label_is_silver"]
    col = None
    for c in silver_col_candidates:
        if c in df.columns:
            col = c
            break
    
    if col is None:
        # If no explicit silver column, return all patterns
        # (they are all candidate rallies)
        return df.copy()
    
    # Filter to silver patterns only
    silver_df = df[df[col] == 1].copy()
    return silver_df


def get_available_symbols() -> List[str]:
    """Get list of symbols with Silver 15m datasets."""
    base = Path("data/ai_datasets")
    if not base.exists():
        return []
    
    symbols = []
    for d in base.iterdir():
        if d.is_dir():
            pattern_file = d / "15m" / "rally_patterns_v1.parquet"
            if pattern_file.exists():
                symbols.append(d.name)
    
    return sorted(symbols)


# ========== V2: SilverEventSummary for Sniper Lab ==========

from dataclasses import dataclass
from typing import Optional

@dataclass
class SilverEventSummary:
    """Summary of a silver rally event for UI display."""
    event_id: str
    event_time: str
    bars_to_peak: int
    quality_score: float
    gain_pct: float
    grade: str  # "Diamond", "Gold", "Silver", "Bronze"


import streamlit as st

@st.cache_data(ttl=120)
def load_silver_events(symbol: str, timeframe: str = "15m") -> List[SilverEventSummary]:
    """
    Load silver rally events as summary objects for Sniper Lab UI.
    
    Returns list of SilverEventSummary sorted by gain descending.
    """
    try:
        df = load_rally_patterns(symbol, timeframe)
    except FileNotFoundError:
        return []
    
    if df.empty:
        return []
    
    # Remove duplicate columns
    df = df.loc[:, ~df.columns.duplicated()]
    
    events = []
    for _, row in df.iterrows():
        # Determine event_id
        event_id = str(row.get("event_time", row.name))
        
        # Event time
        event_time = str(row.get("event_time", ""))
        
        # Bars to peak
        bars_to_peak = int(row.get("feat_bars_to_peak", row.get("label_bars_to_peak", 30)))
        
        # Quality score
        quality_score = float(row.get("feat_quality_score", 0))
        
        # Gain (convert from ratio if needed)
        gain = row.get("label_future_max_gain_pct", 0)
        if gain < 1:
            gain = gain * 100
        
        # Grade
        if row.get("label_is_diamond"):
            grade = "Diamond"
        elif row.get("label_is_gold"):
            grade = "Gold"
        elif row.get("label_is_silver"):
            grade = "Silver"
        else:
            grade = "Bronze"
        
        events.append(SilverEventSummary(
            event_id=event_id,
            event_time=event_time,
            bars_to_peak=bars_to_peak,
            quality_score=quality_score,
            gain_pct=gain,
            grade=grade,
        ))
    
    # Sort by gain descending
    events.sort(key=lambda x: x.gain_pct, reverse=True)
    
    return events


# ========== Alias for generic Sniper use ==========
# RallyEventSummary is an alias for SilverEventSummary (same structure)
RallyEventSummary = SilverEventSummary

def load_rally_events_for_sniper(symbol: str, timeframe: str) -> List[SilverEventSummary]:
    """
    Generic rally event loader for Sniper Lab.
    
    This is an alias for load_silver_events - uses same underlying data
    but provides a more generic interface for future extensions.
    """
    return load_silver_events(symbol, timeframe)
