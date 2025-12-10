"""
Peak Detection V2 - Improved Rally Peak Detection
==================================================

Multi-layer peak validation system for accurate rally top detection.

Features:
- Adaptive window sizing based on volatility
- Multi-pass refinement (finds HIGHEST peak, not just first)
- Volume confirmation
- Retention validation
- Hierarchical detection
"""

import pandas as pd
import numpy as np
from typing import Tuple, Optional, List


def calculate_adaptive_window(atr_pct: float, default: int = 10) -> int:
    """
    Calculate adaptive window radius based on ATR percentage.
    
    Args:
        atr_pct: Average True Range as percentage of price
        default: Default window size
    
    Returns:
        Window radius (bars)
    """
    if atr_pct > 2.0:
        # High volatility - use narrower window
        return 7
    elif atr_pct < 0.5:
        # Low volatility - use wider window
        return 15
    else:
        # Normal volatility - use default
        return default


def find_local_peaks_adaptive(
    df: pd.DataFrame,
    window_radius: int = 10,
    atr_col: str = 'atr'
) -> List[int]:
    """
    Find local peaks using adaptive window if ATR available.
    
    Args:
        df: DataFrame with OHLC data
        window_radius: Base window radius
        atr_col: ATR column name
    
    Returns:
        List of peak indices
    """
    # Calculate average ATR% if available
    if atr_col in df.columns and 'close' in df.columns:
        avg_atr = df[atr_col].mean()
        avg_close = df['close'].mean()
        atr_pct = (avg_atr / avg_close) * 100 if avg_close > 0 else 1.0
        window = calculate_adaptive_window(atr_pct, window_radius)
    else:
        window = window_radius
    
    window_size = (window * 2) + 1
    
    # Find local peaks
    df_copy = df.copy()
    df_copy['rolling_max'] = df_copy['high'].rolling(window=window_size, center=True).max()
    df_copy['is_peak'] = (df_copy['high'] == df_copy['rolling_max']) & df_copy['rolling_max'].notna()
    
    peak_indices = df_copy.index[df_copy['is_peak']].tolist()
    return peak_indices


def validate_peak_volume(
    peak_idx: int,
    df: pd.DataFrame,
    threshold: float = 1.2,
    vol_col: str = 'vol_rel'
) -> bool:
    """
    Validate that peak has volume confirmation.
    
    Args:
        peak_idx: Index of peak bar
        df: DataFrame with volume data
        threshold: Minimum volume relative threshold
        vol_col: Volume relative column name
    
    Returns:
        True if peak has volume confirmation
    """
    if vol_col not in df.columns:
        return True  # Skip validation if no volume data
    
    # Check volume in peak bar and neighbors
    start_idx = max(0, peak_idx - 1)
    end_idx = min(len(df) - 1, peak_idx + 2)
    
    window = df.iloc[start_idx:end_idx]
    if window.empty:
        return False
    
    avg_vol = window[vol_col].mean()
    
    return avg_vol >= threshold


def validate_peak_retention(
    peak_idx: int,
    df: pd.DataFrame,
    lookforward: int = 5,
    min_retention: float = 0.4
) -> Tuple[bool, float]:
    """
    Validate that peak holds (doesn't immediately crash).
    
    Args:
        peak_idx: Index of peak bar
        df: DataFrame with price data
        lookforward: Bars to check after peak
        min_retention: Minimum retention ratio
    
    Returns:
        Tuple of (is_valid, retention_ratio)
    """
    if peak_idx >= len(df) - 1:
        return False, 0.0  # No data after peak
    
    peak_price = df.iloc[peak_idx]['high']
    
    # Get post-peak window
    end_idx = min(len(df), peak_idx + lookforward + 1)
    post_peak = df.iloc[peak_idx + 1:end_idx]
    
    if post_peak.empty:
        return False, 0.0
    
    # Calculate retention (average close / peak high)
    avg_post_close = post_peak['close'].mean()
    retention = avg_post_close / peak_price if peak_price > 0 else 0.0
    
    is_valid = retention >= min_retention
    
    return is_valid, float(retention)


def find_true_peak_multipass(
    dip_idx: int,
    df: pd.DataFrame,
    candidate_peaks: List[int],
    lookforward: int = 20,
    min_retention: float = 0.4,
    volume_threshold: float = 1.2
) -> Optional[Tuple[int, dict]]:
    """
    Find the TRUE peak using multi-pass refinement.
    
    This is the core improvement: instead of taking the FIRST peak,
    we find the HIGHEST peak that passes validations.
    
    Args:
        dip_idx: Index of rally dip (start)
        df: DataFrame with OHLC + volume data
        candidate_peaks: List of potential peak indices
        lookforward: Maximum bars to look forward from dip
        min_retention: Minimum retention ratio for validation
        volume_threshold: Minimum volume threshold
    
    Returns:
        Tuple of (peak_index, validation_details) or None
    """
    # Get peaks within lookforward window
    future_peaks = [p for p in candidate_peaks 
                   if dip_idx < p <= dip_idx + lookforward]
    
    if not future_peaks:
        return None
    
    # Pass 1: Filter by volume
    volume_valid_peaks = []
    for peak in future_peaks:
        if validate_peak_volume(peak, df, volume_threshold):
            volume_valid_peaks.append(peak)
    
    if not volume_valid_peaks:
        # No volume-valid peaks, fallback to all peaks
        volume_valid_peaks = future_peaks
    
    # Pass 2: Filter by retention
    retention_valid_peaks = []
    retention_scores = {}
    
    for peak in volume_valid_peaks:
        is_valid, retention = validate_peak_retention(peak, df, min_retention=min_retention)
        retention_scores[peak] = retention
        
        if is_valid:
            retention_valid_peaks.append(peak)
    
    # If retention filtering removes all peaks, use volume-valid ones
    if not retention_valid_peaks:
        retention_valid_peaks = volume_valid_peaks
    
    # Pass 3: Find HIGHEST peak among valid candidates
    peak_heights = [(p, df.iloc[p]['high']) for p in retention_valid_peaks]
    true_peak_idx, true_peak_price = max(peak_heights, key=lambda x: x[1])
    
    # Compile validation details
    details = {
        'total_candidates': len(future_peaks),
        'volume_valid': len(volume_valid_peaks),
        'retention_valid': len(retention_valid_peaks),
        'peak_price': float(true_peak_price),
        'retention_score': retention_scores.get(true_peak_idx, 0.0),
        'volume_confirmed': true_peak_idx in volume_valid_peaks,
        'retention_confirmed': true_peak_idx in retention_valid_peaks
    }
    
    return true_peak_idx, details


def detect_peaks_v2(
    df: pd.DataFrame,
    dip_idx: int,
    window_radius: int = 10,
    lookforward: int = 20,
    min_retention: float = 0.4,
    volume_threshold: float = 1.2
) -> Optional[Tuple[int, dict]]:
    """
    Main V2 peak detection function.
    
    Combines all validations in hierarchical manner:
    1. Find candidate peaks (adaptive window)
    2. Apply volume filter
    3. Apply retention filter
    4. Return HIGHEST valid peak
    
    Args:
        df: DataFrame with OHLC, volume, ATR data
        dip_idx: Index of rally start (dip)
        window_radius: Base window radius for peak detection
        lookforward: Maximum bars to search forward
        min_retention: Minimum retention threshold (0.4 = 40%)
        volume_threshold: Minimum volume threshold (1.2 = 120% of normal)
    
    Returns:
        Tuple of (peak_index, validation_details) or None if no valid peak
    """
    # Step 1: Find all candidate peaks using adaptive window
    candidate_peaks = find_local_peaks_adaptive(df, window_radius)
    
    if not candidate_peaks:
        return None
    
    # Step 2: Multi-pass refinement
    result = find_true_peak_multipass(
        dip_idx,
        df,
        candidate_peaks,
        lookforward,
        min_retention,
        volume_threshold
    )
    
    return result
