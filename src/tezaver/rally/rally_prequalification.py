"""
Rally Pre-Qualification Module
================================

Calculates momentum and pre-rally conditions to grade rally quality
BEFORE the rally completes.
"""

import pandas as pd
import numpy as np
from typing import Tuple


def calculate_momentum_score(
    pre_rally_bars: pd.DataFrame,
    lookback: int = 5
) -> Tuple[float, dict]:
    """
    Calculate pre-rally momentum score based on 5 bars before rally start.
    
    Args:
        pre_rally_bars: DataFrame with bars before rally (should have exactly 'lookback' rows)
        lookback: Number of bars to analyze
    
    Returns:
        Tuple of (momentum_score, details_dict)
        - momentum_score: 0.0 to 1.0
        - details: breakdown of components
    """
    if len(pre_rally_bars) < lookback:
        return 0.0, {}
    
    details = {}
    score = 0.0
    
    # Component 1: RSI Momentum (0-0.3)
    if 'rsi' in pre_rally_bars.columns:
        rsi_values = pre_rally_bars['rsi'].values
        if len(rsi_values) >= 3:
            rsi_slope = (rsi_values[-1] - rsi_values[0]) / len(rsi_values)
            rsi_is_rising = rsi_values[-1] > rsi_values[0]
            
            # Normalize: slope of +10 = max score
            rsi_component = min(abs(rsi_slope) / 10.0, 1.0) * 0.3 if rsi_is_rising else 0
            score += rsi_component
            details['rsi_momentum'] = float(rsi_component)
            details['rsi_slope'] = float(rsi_slope)
    
    # Component 2: Volume Acceleration (0-0.4)
    if 'vol_rel' in pre_rally_bars.columns:
        vol_values = pre_rally_bars['vol_rel'].values
        if len(vol_values) >= 3:
            # Check if volume is accelerating
            vol_recent = vol_values[-2:].mean()  # Last 2 bars
            vol_earlier = vol_values[:3].mean()  # First 3 bars
            
            if vol_recent > vol_earlier:
                # Increasing volume
                vol_ratio = min(vol_recent / max(vol_earlier, 0.5), 3.0) / 3.0
                vol_component = vol_ratio * 0.4
                score += vol_component
                details['volume_acceleration'] = float(vol_component)
                details['vol_ratio'] = float(vol_recent / max(vol_earlier, 0.5))
    
    # Component 3: MACD Strength (0-0.2)
    if 'macd_hist' in pre_rally_bars.columns:
        macd_values = pre_rally_bars['macd_hist'].values
        if len(macd_values) >= 2:
            macd_current = macd_values[-1]
            macd_prev = macd_values[-2]
            
            # Positive and rising
            if macd_current > 0:
                macd_component = 0.2
            elif macd_prev < 0 and macd_current > macd_prev:
                # Turning positive (bullish cross approaching)
                macd_component = 0.15
            else:
                macd_component = 0
            
            score += macd_component
            details['macd_strength'] = float(macd_component)
    
    # Component 4: Consolidation Tightness (0-0.1)
    if 'high' in pre_rally_bars.columns and 'low' in pre_rally_bars.columns:
        high_values = pre_rally_bars['high'].values
        low_values = pre_rally_bars['low'].values
        
        if len(high_values) >= 3 and len(low_values) >= 3:
            price_range = (max(high_values) - min(low_values)) / min(low_values)
            
            # Tight consolidation (< 3%) gets points
            if price_range < 0.03:
                consolidation_component = 0.1
                details['consolidation_breakout'] = True
            else:
                consolidation_component = 0
                details['consolidation_breakout'] = False
            
            score += consolidation_component
            details['consolidation_score'] = float(consolidation_component)
            details['price_range_pct'] = float(price_range * 100)
    
    return float(min(score, 1.0)), details


def pre_qualify_rally(
    df: pd.DataFrame,
    event_idx: int,
    lookback: int = 5
) -> dict:
    """
    Pre-qualify a rally based on conditions at the dip/event.
    
    NOTE: This function signature has been updated to match scanner usage.
    Old signature: pre_qualify_rally(event_idx, df, lookback)
    New signature: pre_qualify_rally(df, event_idx, lookback)
    """
    # Get event row (dip)
    if event_idx >= len(df):
        return {}
    
    event_row = df.iloc[event_idx]
    
    # Extract key metrics at dip (simple version - no momentum calculation for now)
    result = {
        'rsi_15m': float(event_row.get('rsi', 0)),
        'macd_histogram_15m': float(event_row.get('macd_hist', 0)),
        'volume': float(event_row.get('volume', 0)),
        'vol_rel': float(event_row.get('vol_rel', 1.0)),
    }
    
    # Calculate simple momentum score
    rsi = result['rsi_15m']
    macd_hist = result['macd_histogram_15m']
    vol_rel = result['vol_rel']
    
    # Momentum scoring (simplified)
    score = 0.0
    
    # RSI oversold bonus
    if rsi < 40:
        score += 0.3
    elif rsi < 50:
        score += 0.15
    
    # MACD turning positive
    if macd_hist > 0:
        score += 0.3
    elif macd_hist > -0.5:
        score += 0.15
    
    # Volume confirmation
    if vol_rel > 1.2:
        score += 0.4
    elif vol_rel > 1.0:
        score += 0.2
    
    result['momentum_score'] = min(score, 1.0)
    
    return result
