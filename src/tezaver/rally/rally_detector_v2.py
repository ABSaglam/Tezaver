"""
Rally Detector v2 - Micro Booster
==================================

Lab/experimental rally detection layer for catching short, intense 15m rallies.

This module provides a "booster" detection mechanism that complements the
core scanner by using momentum ignition + volume spike anchor approach.

**Design Goals:**
- Catch short rallies missed by core scanner (e.g., SOL Dec 2, 14:30-18:30, ~6%)
- Don't explode event count (controlled growth)
- Independent from core scanner (lab use, not production)
- Preserve Oracle v1 dataset (77 rallies, read-only)

**Approach:**
1. Find volume spike anchors
2. Look back 2-3 bars for momentum ignition point
3. Search forward (max 24 bars) for peak
4. Apply strict filters (gain%, bars, vol_rel range)
5. Return booster events (additive, not replacing)
"""

from dataclasses import dataclass
from typing import Optional, List, Dict
import pandas as pd
import numpy as np

from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


@dataclass
class RallyDetectorV2Params:
    """
    Parameters for Rally Detector v2 micro-booster.
    
    Tuned for catching short 15m rallies (4-24 bars, 5.5%+ gain).
    """
    # Gain thresholds (tuned to keep event count <400)
    micro_min_gain_pct: float = 0.055  # 5.5% minimum (slightly stricter)
    
    # Time constraints
    max_micro_bars: int = 24  # Max bars from ignition to peak
    min_bars_to_peak: int = 4  # Min bars (filter noise)
    
    # Volume spike filters
    spike_min_vol_rel: float = 1.5  # Min volume ratio (filter weak spikes)
    spike_max_vol_rel: float = 10.0  # Max volume ratio (filter manic spikes)
    
    # Ignition detection
    ignition_back_bars: int = 3  # How many bars before spike to look
    
    # RSI filters (optional, set to None to disable)
    min_rsi: Optional[float] = 30.0  # Min RSI at ignition (avoid over-sold extremes)
    max_rsi: Optional[float] = 80.0  # Max RSI at ignition (avoid over-bought)


def deduplicate_micro_rallies(df: pd.DataFrame, timeframe: str = "15m") -> pd.DataFrame:
    """
    Rally Detector v2 çıktısındaki GERÇEK kopyaları tekilleştirir.
    
    REV.06 Soft Dedup: Sadece çok yakın, benzer olayları birleştirir.
    
    Kopya tanımı (HEPSİ gerekli):
      - Aynı (veya çok yakın) peak_time (peak_bucket)
      - event_time farkı küçük (<= 3 bar)
      - future_max_gain_pct benzer (< 1% fark)
      - bars_to_peak benzer (<= 2 bar fark)
    
    Eğer event_time farkı > 3 bar ise → Ayrı trade fırsatı olarak KORU.
    """
    if df.empty:
        return df

    # 1. Delta calculation
    if timeframe == "15m":
        bar_delta = pd.Timedelta(minutes=15)
    elif timeframe == "1h":
        bar_delta = pd.Timedelta(hours=1)
    elif timeframe == "4h":
        bar_delta = pd.Timedelta(hours=4)
    else:
        bar_delta = pd.Timedelta(minutes=15)
    
    # 2. Calculate peak_time if not exists
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df['event_time']):
        df['event_time'] = pd.to_datetime(df['event_time'])

    df['peak_time'] = df['event_time'] + (df['bars_to_peak'] * bar_delta)
    
    # 3. Create peak_bucket (rounded to nearest bar)
    df['peak_bucket'] = df['peak_time'].dt.floor(bar_delta)
    
    # 4. Group by peak_bucket and apply soft dedup within each group
    groups = df.groupby('peak_bucket')
    
    records_to_keep = []
    
    for _, group in groups:
        if len(group) == 1:
            # No duplicates in this bucket
            records_to_keep.append(group.iloc[0])
            continue
        
        # Sort by event_time to process chronologically
        group = group.sort_values('event_time').reset_index(drop=True)
        
        # Track which events to keep (start with all)
        keep_mask = [True] * len(group)
        
        # Compare consecutive events
        for i in range(len(group)):
            if not keep_mask[i]:
                continue  # Already marked as duplicate
            
            for j in range(i + 1, len(group)):
                if not keep_mask[j]:
                    continue
                
                # Calculate differences
                event_time_diff = (group.loc[j, 'event_time'] - group.loc[i, 'event_time']) / bar_delta
                gain_diff = abs(group.loc[j, 'future_max_gain_pct'] - group.loc[i, 'future_max_gain_pct'])
                bars_diff = abs(group.loc[j, 'bars_to_peak'] - group.loc[i, 'bars_to_peak'])
                
                # SOFT CRITERIA: All must be true to consider duplicate
                is_duplicate = (
                    event_time_diff <= 3 and  # Close in time
                    gain_diff < 0.01 and      # Similar gain (< 1%)
                    bars_diff <= 2            # Similar duration
                )
                
                if is_duplicate:
                    # Keep the one with higher gain, or earlier if equal
                    if group.loc[j, 'future_max_gain_pct'] > group.loc[i, 'future_max_gain_pct']:
                        keep_mask[i] = False
                        break  # i is duplicate, move to next i
                    else:
                        keep_mask[j] = False  # j is duplicate
        
        # Add kept events
        for idx, keep in enumerate(keep_mask):
            if keep:
                records_to_keep.append(group.iloc[idx])
    
    # 5. Reconstruct DataFrame
    if not records_to_keep:
        return pd.DataFrame()
    
    df_out = pd.DataFrame(records_to_keep)
    df_out = df_out.drop(columns=['peak_time', 'peak_bucket'], errors='ignore')
    df_out = df_out.sort_values('event_time').reset_index(drop=True)
    
    return df_out


def detect_rallies_v2_micro_booster(
    df_15m: pd.DataFrame,
    params: Optional[RallyDetectorV2Params] = None,
    deduplicate: bool = False,  # REV.06: Optional, default OFF
) -> pd.DataFrame:
    """
    Rally Detector v2 - Micro Booster.
    
    Detects short, intense 15m rallies using momentum ignition approach.
    Designed to catch rallies like SOL Dec 2 (14:30-18:30, ~6%, 16 bars).
    
    **Independent Operation:**
    - Does NOT call core scanner
    - Does NOT modify Oracle v1 dataset
    - Returns only booster events
    
    **Algorithm:**
    1. Find volume spike bars (vol_spike == True)
    2. For each spike, find ignition point (2-3 bars before)
    3. Search forward for peak (max 24 bars)
    4. Apply filters (gain%, bars, vol_rel)
    5. Return qualifying events
    
    Args:
        df_15m: 15m OHLCV + features DataFrame
                Required columns: timestamp, open, high, low, close,
                                  vol_rel, vol_spike, rsi (optional)
        params: Detection parameters (uses defaults if None)
        deduplicate: If True, apply soft dedup to remove close duplicates.
                     Default False (keep all raw events).
    
    Returns:
        DataFrame with booster rally events
        Columns: event_time, entry_index, peak_index, bars_to_peak,
                 future_max_gain_pct, source, vol_rel, rsi (if available)
    
    Example:
        >>> df = load_sol_15m_data()
        >>> events = detect_rallies_v2_micro_booster(df)
        >>> dec2_events = events[events['event_time'].dt.date == '2025-12-02']
    """
    if params is None:
        params = RallyDetectorV2Params()
    
    if df_15m.empty:
        logger.warning("Empty DataFrame provided to v2 booster")
        return pd.DataFrame()
    
    # Required columns check
    required_cols = ['timestamp', 'open', 'high', 'low', 'close']
    missing = [c for c in required_cols if c not in df_15m.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    logger.info(f"V2 Booster starting: {len(df_15m)} bars")
    
    # Ensure index is integer-based for indexing
    df = df_15m.reset_index(drop=True).copy()
    
    # Find volume spike anchors
    has_vol_spike = 'vol_spike' in df.columns
    has_vol_rel = 'vol_rel' in df.columns
    has_rsi = 'rsi' in df.columns
    
    if has_vol_spike:
        spike_mask = df['vol_spike'] == True
        spike_indices = df.index[spike_mask].tolist()
        logger.info(f"Found {len(spike_indices)} volume spike anchors")
    else:
        # Fallback: use vol_rel if vol_spike not available
        if has_vol_rel:
            spike_mask = df['vol_rel'] >= params.spike_min_vol_rel
            spike_indices = df.index[spike_mask].tolist()
            logger.info(f"Using vol_rel threshold: {len(spike_indices)} potential spikes")
        else:
            logger.warning("No vol_spike or vol_rel column - cannot proceed")
            return pd.DataFrame()
    
    records = []
    
    # Process each spike anchor
    for spike_idx in spike_indices:
        spike_pos = int(spike_idx)
        
        # Volume filter
        if has_vol_rel:
            vol_rel_val = df.at[spike_pos, 'vol_rel']
            if not (params.spike_min_vol_rel <= vol_rel_val <= params.spike_max_vol_rel):
                continue
        
        # Find ignition window (2-3 bars before spike)
        ignition_start = max(0, spike_pos - params.ignition_back_bars - 2)
        ignition_end = max(0, spike_pos - 1)
        
        if ignition_start >= ignition_end:
            continue
        
        # Find ignition point (lowest close in window)
        ignition_window = df.loc[ignition_start:ignition_end]
        if ignition_window.empty:
            continue
        
        ignition_idx = ignition_window['close'].idxmin()
        ignition_pos = int(ignition_idx)
        
        entry_price = df.at[ignition_pos, 'close']
        
        # RSI filter at ignition (if available)
        if has_rsi and params.min_rsi is not None and params.max_rsi is not None:
            rsi_val = df.at[ignition_pos, 'rsi']
            if not (params.min_rsi <= rsi_val <= params.max_rsi):
                continue
        
        # Find peak (forward search, max 24 bars)
        peak_window_end = min(len(df) - 1, ignition_pos + params.max_micro_bars)
        if peak_window_end <= ignition_pos:
            continue
        
        peak_window = df.loc[ignition_pos:peak_window_end]
        peak_idx = peak_window['close'].idxmax()
        peak_pos = int(peak_idx)
        
        peak_price = df.at[peak_pos, 'close']
        
        # Calculate metrics
        if entry_price <= 0:
            continue
        
        future_max_gain_pct = (peak_price / entry_price) - 1.0
        bars_to_peak = peak_pos - ignition_pos
        
        # Filters
        if future_max_gain_pct < params.micro_min_gain_pct:
            continue
        
        if not (params.min_bars_to_peak <= bars_to_peak <= params.max_micro_bars):
            continue
        
        # Create event record
        record = {
            'event_time': df.at[ignition_pos, 'timestamp'],
            'entry_index': ignition_pos,
            'peak_index': peak_pos,
            'bars_to_peak': bars_to_peak,
            'future_max_gain_pct': future_max_gain_pct,
            'source': 'v2_micro_booster',
        }
        
        # Add optional context
        if has_vol_rel:
            record['vol_rel'] = df.at[spike_pos, 'vol_rel']
        if has_rsi:
            record['rsi'] = df.at[ignition_pos, 'rsi']
        
        records.append(record)
    
    # Create result DataFrame
    if not records:
        logger.info("V2 Booster: No qualifying events found")
        return pd.DataFrame()
    
    df_events = pd.DataFrame.from_records(records)
    
    # Sort by event_time
    df_events = df_events.sort_values('event_time').reset_index(drop=True)
    
    logger.info(f"V2 Booster found {len(df_events)} raw events")

    # Apply Deduplication (Optional - REV.06)
    if deduplicate:
        df_events = deduplicate_micro_rallies(df_events, timeframe="15m")
        logger.info(f"V2 Booster: Dedup applied, {len(df_events)} events after soft dedup")
    else:
        logger.info("V2 Booster: Dedup skipped (deduplicate=False)")
    
    logger.info(f"V2 Booster completed: {len(df_events)} events detected")

    
    return df_events
