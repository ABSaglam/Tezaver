"""
Rally Miner Engine (Peak-Mining v1)
Core logic for historical rally discovery and classification.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Optional
from datetime import timedelta

def mine_rallies(
    df: pd.DataFrame, 
    symbol: str, 
    max_window: int = 96, 
    min_gain: float = 0.05
) -> List[Dict]:
    """
    Identifies non-overlapping price rallies using the Peak-Mining algorithm.
    Prioritizes 'Intensity' (Gain / Duration).
    """
    if df.empty:
        return []

    candidates = []
    prices_high = df['high'].values
    prices_low = df['low'].values
    times = df['datetime'].values
    n = len(df)
    
    # Scan every 5 bars for efficiency (can be 1 for maximum precision)
    for i in range(0, n - 10, 5):
        window_end = min(i + max_window, n)
        
        # 1. Find local Peak (Max High in window)
        win_highs = prices_high[i:window_end]
        max_h_idx_local = np.argmax(win_highs)
        max_h = win_highs[max_h_idx_local]
        max_h_global = i + max_h_idx_local
        
        # 2. Find local Source (Min Low before Peak)
        win_lows_before = prices_low[i:max_h_global + 1]
        if len(win_lows_before) < 2:
            continue
            
        min_l_idx_local = np.argmin(win_lows_before)
        min_l = win_lows_before[min_l_idx_local]
        min_l_global = i + min_l_idx_local
        
        duration = max_h_global - min_l_global + 1
        if duration < 2:
            continue
            
        gain = (max_h / min_l) - 1
        if gain >= min_gain:
            candidates.append({
                'symbol': symbol,
                'start_idx': min_l_global,
                'end_idx': max_h_global,
                'start_time': times[min_l_global],
                'end_time': times[max_h_global],
                'gain': gain * 100,
                'bars': int(duration),
                'intensity': (gain * 100) / duration,
                'low': float(min_l),
                'high': float(max_h)
            })

    # 3. Sort by Intensity (Hızlı ve etkili olanlar önce)
    candidates.sort(key=lambda x: x['intensity'], reverse=True)
    
    final_rallies = []
    used_indices = set()
    
    for c in candidates:
        # Check for overlap
        r = set(range(c['start_idx'], c['end_idx'] + 1))
        if not (r & used_indices):
            final_rallies.append(c)
            used_indices.update(r)
            
    return final_rallies

def classify_tier(gain: float) -> str:
    """Classifies a rally into tiers based on gain percentage."""
    if gain >= 30: return 'DIAMOND'
    if gain >= 20: return 'GOLD'
    if gain >= 10: return 'SILVER'
    if gain >= 5: return 'BRONZE'
    return 'IRON'
