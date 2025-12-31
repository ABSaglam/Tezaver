
import pandas as pd
import numpy as np
import logging
from typing import List, Optional, Dict, Any, Tuple
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def multi_pass_detection(
    df: pd.DataFrame,
    window_sizes: List[int] = [5, 15, 30],
    min_gain: float = 0.05,
    max_lookahead: int = 100
) -> List[Tuple[int, int, float]]:
    """
    Çoklu pencere boyutuyla rally tespiti.
    Diamond öncelikli, çakışan rallilerde en yüksek kazançlı kazanır.
    """
    all_rallies = []
    
    for window_radius in window_sizes:
        window_size = (window_radius * 2) + 1
        
        df['rolling_min'] = df['low'].rolling(window=window_size, center=True).min()
        df['is_dip'] = (df['low'] == df['rolling_min']) & df['rolling_min'].notna()
        
        df['rolling_max'] = df['high'].rolling(window=window_size, center=True).max()
        df['is_peak'] = (df['high'] == df['rolling_max']) & df['rolling_max'].notna()
        
        dip_indices = df.index[df['is_dip']].tolist()
        peak_indices = df.index[df['is_peak']].tolist()
        
        for dip_idx in dip_indices:
            future_peaks = [p for p in peak_indices if dip_idx < p <= dip_idx + max_lookahead]
            
            if not future_peaks:
                continue
            
            dip_price = df.at[dip_idx, 'low']
            if dip_price <= 0:
                continue
            
            best_peak_idx = None
            best_gain = 0
            
            for peak_idx in future_peaks:
                peak_price = df.at[peak_idx, 'high']
                gain_pct = (peak_price - dip_price) / dip_price
                
                if gain_pct > best_gain:
                    best_gain = gain_pct
                    best_peak_idx = peak_idx
            
            if best_gain >= min_gain and best_peak_idx is not None:
                all_rallies.append((dip_idx, best_peak_idx, best_gain))
    
    if not all_rallies:
        return []
    
    # Tekrarları temizle
    df_rallies = pd.DataFrame(all_rallies, columns=['dip_idx', 'peak_idx', 'gain_pct'])
    df_dedup = df_rallies.sort_values('gain_pct', ascending=False).groupby('peak_idx').first().reset_index()
    
    # Diamond öncelikli semantic lockout
    df_dedup = df_dedup.sort_values('gain_pct', ascending=False)
    
    final_rallies = []
    covered_ranges = []
    
    for _, row in df_dedup.iterrows():
        dip_idx = int(row['dip_idx'])
        peak_idx = int(row['peak_idx'])
        
        is_overlapping = False
        for start, end in covered_ranges:
            if not (dip_idx > end or peak_idx < start):
                is_overlapping = True
                break
        
        if not is_overlapping:
            final_rallies.append((dip_idx, peak_idx, row['gain_pct']))
            covered_ranges.append((dip_idx, peak_idx))
    
    final_rallies.sort(key=lambda x: x[0])
    
    return final_rallies


def find_impulse_zone(
    df: pd.DataFrame,
    dip_idx: int,
    peak_idx: int,
    window_size: int = 10
) -> Tuple[int, int, float]:
    """
    Yoğun Bölge (Impulse Zone) Tespiti:
    Rally içindeki en yoğun hareketin olduğu pencereyi bul.
    """
    if peak_idx - dip_idx <= window_size:
        dip_price = df.at[dip_idx, 'low']
        peak_price = df.at[peak_idx, 'high']
        gain = (peak_price - dip_price) / dip_price if dip_price > 0 else 0
        return dip_idx, peak_idx, gain
    
    best_start = dip_idx
    best_gain = 0
    
    for i in range(dip_idx, peak_idx - window_size + 1):
        window_low = df.loc[i:i+window_size, 'low'].min()
        window_high = df.loc[i:i+window_size, 'high'].max()
        window_gain = (window_high - window_low) / window_low if window_low > 0 else 0
        
        if window_gain > best_gain:
            best_gain = window_gain
            best_start = i
    
    best_end = min(best_start + window_size, peak_idx)
    
    return best_start, best_end, best_gain


def detect_rallies_oracle_mode(
    df: pd.DataFrame,
    window_radius: int = 10,
    min_gain: float = 0.05,
    event_gap: int = 3,
    max_peak_lookahead: int = 60
) -> pd.DataFrame:
    """
    Detects rallies using Precision Mining with Impulse Zone detection.
    
    UPGRADED from basic rolling extrema to:
    1. Multi-pass detection (3 window sizes: 5, 15, 30)
    2. Diamond-priority lockout (highest gain wins in overlaps)
    3. Impulse zone based entry/exit (10-bar concentrated movement)
    
    Args:
        df: DataFrame with 'high', 'low', 'close', 'timestamp'
        window_radius: Base window (will use 5, 15, 30 multi-pass)
        min_gain: Minimum gain (e.g. 0.05 for 5%)
        event_gap: (legacy, not used in new logic)
        max_peak_lookahead: Max bars to look ahead (default 60 → 100)
        
    Returns:
        DataFrame with rally events: 
        [event_index, event_time, future_max_gain_pct, bars_to_peak, peak_index, dip_price,
         entry_idx, exit_idx, impulse_gain_pct]
    """
    if df.empty:
        return pd.DataFrame()
        
    if 'high' not in df.columns or 'low' not in df.columns:
        logger.warning("Missing high/low columns in detection")
        return pd.DataFrame()
        
    # Prepare timestamp
    if 'timestamp' not in df.columns:
        if 'open_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['open_time'])
        else:
            df['timestamp'] = df.index
    
    df = df.reset_index(drop=True)
    
    # Multi-pass detection
    raw_rallies = multi_pass_detection(df, min_gain=min_gain, max_lookahead=max(100, max_peak_lookahead))
    
    if not raw_rallies:
        return pd.DataFrame()
    
    events = []
    
    for dip_idx, peak_idx, raw_gain in raw_rallies:
        # Impulse zone (yoğun bölge)
        impulse_start, impulse_end, impulse_gain = find_impulse_zone(df, dip_idx, peak_idx, window_size=10)
        
        # Entry = impulse başlangıcından 1 bar önce
        entry_idx = max(dip_idx, impulse_start - 1)
        exit_idx = impulse_end
        
        bars_to_peak = peak_idx - dip_idx  # Eski sistemle uyumlu
        
        events.append({
            'event_index': entry_idx,  # Giriş noktası (impulse bazlı)
            'event_time': df.at[entry_idx, 'timestamp'],
            'future_max_gain_pct': raw_gain,  # Ham dip-peak kazancı (tier için)
            'bars_to_peak': bars_to_peak,
            'peak_index': peak_idx,
            'dip_price': df.at[dip_idx, 'low'],
            # Yeni alanlar
            'raw_dip_idx': dip_idx,
            'raw_peak_idx': peak_idx,
            'entry_idx': entry_idx,
            'exit_idx': exit_idx,
            'impulse_gain_pct': impulse_gain,
        })
    
    return pd.DataFrame(events)
