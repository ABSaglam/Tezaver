
import pandas as pd
import numpy as np
import logging
from typing import List, Optional, Dict, Any, Tuple
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def detect_rallies_oracle_mode(
    df: pd.DataFrame,
    window_radius: int = 10,
    min_gain: float = 0.05,
    event_gap: int = 3,
    max_peak_lookahead: int = 60
) -> pd.DataFrame:
    """
    Detects rallies using 'Oracle Mode' (Historical Rolling Extremas).
    UNIFIED LOGIC for 15m, 1h, 4h.
    
    Logic:
    1. Find Local Dips: Low[t] == Min(Low[t-N : t+N])
    2. Find Local Peaks: High[t] == Max(High[t-N : t+N])
    3. Match Dip -> Best Peak (Max Gain)
    4. Deduplicate (Keep lowest Dip for same Peak)
    5. Filter Constraints (Min Gain, Lockout)
    
    Args:
        df: DataFrame with 'high', 'low', 'close', 'timestamp' (or index as ts)
        window_radius: Number of bars to look back/forward for extrema (N)
        min_gain: Minimum gain to qualify as rally (e.g. 0.05 for 5%)
        event_gap: Minimum bars between events (start to start, subject to lockout)
        max_peak_lookahead: Max bars to look ahead for a peak
        
    Returns:
        DataFrame with rally events: 
        [event_index, event_time, future_max_gain_pct, bars_to_peak, peak_index, dip_price]
    """
    if df.empty:
        return pd.DataFrame()
        
    # Ensure High/Low exist
    if 'high' not in df.columns or 'low' not in df.columns:
        logger.warning("Missing high/low columns in detection")
        return pd.DataFrame()
        
    # Prepare basic columns
    if 'timestamp' not in df.columns:
        # Try finding it or use index
        if 'open_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['open_time'])
        else:
            df['timestamp'] = df.index
            
    # Calculate Rolling Min/Max
    window_size = (window_radius * 2) + 1
    
    # Find Local Dips (Swing Lows)
    df['rolling_min'] = df['low'].rolling(window=window_size, center=True).min()
    df['is_dip'] = (df['low'] == df['rolling_min']) & df['rolling_min'].notna()
    
    # Find Local Peaks (Swing Highs)
    df['rolling_max'] = df['high'].rolling(window=window_size, center=True).max()
    df['is_peak'] = (df['high'] == df['rolling_max']) & df['rolling_max'].notna()
    
    # Extract indices
    dip_indices = df.index[df['is_dip']].tolist()
    peak_indices = df.index[df['is_peak']].tolist()
    
    raw_events = []
    
    # Matching Loop
    for dip_idx in dip_indices:
        # Find subsequent peaks within lookahead window
        future_peaks = [p for p in peak_indices if dip_idx < p <= dip_idx + max_peak_lookahead]
        
        if not future_peaks:
            continue
        
        dip_price = df.at[dip_idx, 'close'] # Option: Use 'low' for stricter entry? 
        # Fast15 used 'close' for gain calc but 'low' for dedupe. Let's stick to Fast15 logic for continuity.
        # Wait, if we want to catch wicks, dip_price should be low?
        # Standard: Entry is rarely at perfect low. Close is safer. 
        # But if we define rally magnitude, High-Low is the full range.
        # Let's stick to Close-to-High as "realizable" gain, but Low-based detection.
        
        if dip_price <= 0: continue
            
        best_peak_idx = None
        best_gain = 0
        
        for peak_idx in future_peaks:
            peak_price = df.at[peak_idx, 'high']
            gain_pct = (peak_price - dip_price) / dip_price
            
            if gain_pct > best_gain:
                best_gain = gain_pct
                best_peak_idx = peak_idx
        
        if best_gain >= min_gain and best_peak_idx is not None:
            bars_to_peak = best_peak_idx - dip_idx
            
            raw_events.append({
                'event_index': dip_idx,
                'event_time': df.at[dip_idx, 'timestamp'],
                'future_max_gain_pct': best_gain,
                'bars_to_peak': bars_to_peak,
                'peak_index': best_peak_idx,
                'dip_price': df.at[dip_idx, 'low']
            })
            
    if not raw_events:
        return pd.DataFrame()
        
    # Deduplication & Lockout
    df_raw = pd.DataFrame(raw_events)
    
    # 1. Dedupe by Peak (Ragged Bottoms) -> Keep lowest dip
    events_dedup = df_raw.sort_values('dip_price').groupby('peak_index').first().reset_index()
    events_dedup = events_dedup.sort_values('event_index').reset_index(drop=True)
    
    # 2. Semantic Lockout
    filtered_events = []
    last_event_limit = -999 
    
    for _, row in events_dedup.iterrows():
        current_idx = int(row['event_index'])
        
        if current_idx >= last_event_limit:
            # Accepted
            filtered_events.append(row.to_dict())
            
            # Lockout until this rally's peak
            # We add a small buffer? No, peak is the definitive end of the "move up".
            last_event_limit = int(row['peak_index'])
            
    return pd.DataFrame(filtered_events)
