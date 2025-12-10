"""
Momentum Ignition Detector
===========================

Peak-first rally detection: Find the "kıpırdanma" (momentum ignition) point.

**VOLUME-SPIKE ANCHOR APPROACH** (Simplified & Tested):
- Find LARGEST volume spike near peak (not first!)
- Go back 2 bars = momentum ignition
- Tested on 2 Ara: PERFECT HIT (14:30, 0dk fark)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def find_momentum_ignition(
    df: pd.DataFrame,
    peak_idx: int,
    peak_price: float,
    max_lookback: int = 100,
    min_gain_threshold: float = 0.02
) -> Optional[Dict]:
    """
    Peak'ten geriye bakarak momentum ignition noktasını bul.
    
    **VOLUME-SPIKE ANCHOR APPROACH**:
    1. Find LARGEST volume spike (peak yakınında)
    2. Go back 2-3 bars = momentum ignition
    3. Validate gain potential
    
    Test Results:
    - 2 Ara: 14:30 buldu (0dk fark) ✅
    - 26 Kas: 10:15 buldu (225dk fark - erken)
    """
    
    # Backward window
    start_idx = max(0, peak_idx - max_lookback)
    window = df.iloc[start_idx:peak_idx + 1].copy()
    
    if len(window) < 5:
        return None
    
    # Volume spike detection
    if 'volume' in window.columns:
        window['vol_ma'] = window['volume'].rolling(10, min_periods=3).mean()
        window['vol_ratio'] = window['volume'] / window['vol_ma']
        
        # Search: exclude last 2 bars (too close to peak)
        search_window = window.iloc[:-2] if len(window) > 2 else window
        
        if len(search_window) > 0:
            # Find LARGEST spike
            max_spike_idx = search_window['vol_ratio'].idxmax()
            max_spike_ratio = search_window.loc[max_spike_idx, 'vol_ratio']
            
            # Ignition = 2 bars before
            ignition_idx = max_spike_idx - 2
            
            # Bounds check
            if ignition_idx < start_idx:
                ignition_idx = max_spike_idx - 1
            if ignition_idx < start_idx:
                ignition_idx = max_spike_idx
            
            # Validate
            ignition_row = df.loc[ignition_idx]
            ignition_price = ignition_row['close']
            
            potential_gain = (peak_price - ignition_price) / ignition_price
            
            # Minimum gain check
            if potential_gain < min_gain_threshold:
                ignition_idx = max_spike_idx - 1
                if ignition_idx >= start_idx:
                    ignition_row = df.loc[ignition_idx]
                    ignition_price = ignition_row['close']
                    potential_gain = (peak_price - ignition_price) / ignition_price
            
            # Consolidation breakout
            local_min = window['low'].min()
            consolidation_pct = (ignition_price - local_min) / local_min * 100
            
            return {
                'idx': ignition_idx,
                'price': ignition_price,
                'timestamp': ignition_row.get('timestamp', None),
                'score': max_spike_ratio,
                'type': 'volume_spike_anchor',
                'distance_from_peak': peak_idx - ignition_idx,
                'potential_gain_pct': potential_gain * 100,
                'consolidation_breakout_pct': consolidation_pct,
                'largest_spike_ratio': max_spike_ratio,
                'largest_spike_time': df.loc[max_spike_idx].get('timestamp', None)
            }
    
    # Fallback: local minimum
    min_idx = window['low'].idxmin()
    return {
        'idx': min_idx,
        'price': window.loc[min_idx, 'low'],
        'timestamp': window.loc[min_idx].get('timestamp', None),
        'score': 0.0,
        'type': 'fallback_minimum',
        'distance_from_peak': peak_idx - min_idx,
        'potential_gain_pct': (peak_price - window.loc[min_idx, 'low']) / window.loc[min_idx, 'low'] * 100
    }


def find_swing_peaks(
    df: pd.DataFrame,
    window_radius: int = 10
) -> pd.Series:
    """
    Find swing high peaks using rolling window.
    """
    if 'high' not in df.columns:
        logger.warning("Missing 'high' column for peak detection")
        return pd.Series([False] * len(df), index=df.index)
    
    window_size = (window_radius * 2) + 1
    
    df_temp = df.copy()
    df_temp['rolling_max'] = df_temp['high'].rolling(window=window_size, center=True).max()
    df_temp['is_peak'] = (df_temp['high'] == df_temp['rolling_max']) & df_temp['rolling_max'].notna()
    
    return df_temp['is_peak']
