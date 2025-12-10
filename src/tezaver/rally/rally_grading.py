"""
Rally Grading System - Diamond/Gold/Silver/Bronze Classification

Grades rallies based on:
- Gain (35%)
- Quality (25%)
- Momentum (20%)
- Context/Multi-TF (15%)
- Retention (5%)
"""

import pandas as pd
from typing import Tuple, Dict


def calculate_context_score(rally: pd.Series) -> float:
    """
    Calculate multi-timeframe context score (0-1).
    
    Components:
    - 1h trend alignment (40%)
    - 4h trend alignment (30%)
    - 1d trend alignment (20%)
    - Rally Radar status (10%)
    """
    score = 0.0
    
    # Trend alignment (check trend_soul values)
    trend_1h = rally.get('trend_soul_1h', 0)
    trend_4h = rally.get('trend_soul_4h', 0)
    trend_1d = rally.get('trend_soul_1d', 0)
    
    # Normalize trend_soul to 0-1 (assuming it's -100 to +100)
    if pd.notna(trend_1h):
        score += (max(0, trend_1h) / 100) * 0.40
    if pd.notna(trend_4h):
        score += (max(0, trend_4h) / 100) * 0.30
    if pd.notna(trend_1d):
        score += (max(0, trend_1d) / 100) * 0.20
    
    # Rally Radar (if available) - placeholder for future integration
    # radar_status = rally.get('radar_status', 'COLD')
    # if radar_status == 'HOT': score += 0.10
    # elif radar_status == 'WARM': score += 0.05
    
    return min(score, 1.0)


def calculate_overall_score(rally: pd.Series, use_context: bool = False) -> Tuple[float, Dict[str, float]]:
    """
    Calculate weighted overall score for rally grading.
    
    Args:
        rally: Rally data series
        use_context: If True, include multi-TF context (requires trend_soul data)
    
    Returns:
        Tuple of (total_score, component_scores_dict)
    """
    # Component scores (normalized to 0-100)
    gain = rally.get('future_max_gain_pct', 0) * 100
    quality = rally.get('quality_score', 0)
    momentum = rally.get('momentum_score', 0) * 100
    retention = rally.get('retention_10_pct', 0) if pd.notna(rally.get('retention_10_pct')) else 0
    
    # Normalize gain (cap at 20% = 100 points, more realistic)
    gain_score = min(gain / 20 * 100, 100)
    
    if use_context:
        # WITH context (if trend_soul available)
        context = calculate_context_score(rally) * 100
        components = {
            'gain': gain_score * 0.35,
            'quality': quality * 0.25,
            'momentum': momentum * 0.20,
            'context': context * 0.15,
            'retention': retention * 0.05
        }
    else:
        # WITHOUT context (fallback - redistribute weights)
        components = {
            'gain': gain_score * 0.45,        # 35% + 10% from context
            'quality': quality * 0.30,        # 25% + 5% from context  
            'momentum': momentum * 0.20,      # Unchanged
            'retention': retention * 0.05     # Unchanged
        }
    
    total_score = sum(components.values())
    
    return total_score, components


def grade_rally(rally: pd.Series, use_context: bool = False) -> str:
    """
    Assign grade tier torally based on overall score.
    
    Adjusted tiers (more realistic without context):
    - 💎 Diamond: Score >= 85
    - 🥇 Gold: Score >= 70
    - 🥈 Silver: Score >= 55
    - 🥉 Bronze: Score < 55
    """
    score, _ = calculate_overall_score(rally, use_context)
    
    if score >= 85:
        return "💎 Diamond"
    elif score >= 70:
        return "🥇 Gold"
    elif score >= 55:
        return "🥈 Silver"
    else:
        return "🥉 Bronze"


def enrich_rallies_with_grades(rallies_df: pd.DataFrame, use_context: bool = False) -> pd.DataFrame:
    """
    Add grading columns to rally dataframe.
    
    Args:
        rallies_df: Rally dataframe
        use_context: If True, include multi-TF context in scoring
    
    Adds:
    - rally_grade: Diamond/Gold/Silver/Bronze
    - overall_score: 0-100 score
    - score_components: Dictionary of component scores
    """
    df = rallies_df.copy()
    
    # Calculate grades and scores
    df['rally_grade'] = df.apply(lambda r: grade_rally(r, use_context), axis=1)
    
    scores_and_components = df.apply(lambda r: calculate_overall_score(r, use_context), axis=1)
    df['overall_score'] = scores_and_components.apply(lambda x: x[0])
    df['score_breakdown'] = scores_and_components.apply(lambda x: x[1])
    
    return df


def analyze_tier_patterns(rallies_df: pd.DataFrame) -> Dict[str, Dict]:
    """
    Analyze common patterns within each grade tier.
    
    Returns dictionary with tier-specific statistics.
    """
    analysis = {}
    
    for grade in ["💎 Diamond", "🥇 Gold", "🥈 Silver", "🥉 Bronze"]:
        tier_rallies = rallies_df[rallies_df['rally_grade'] == grade]
        
        if len(tier_rallies) == 0:
            continue
        
        analysis[grade] = {
            'count': len(tier_rallies),
            'avg_gain_pct': tier_rallies['future_max_gain_pct'].mean() * 100,
            'avg_quality': tier_rallies['quality_score'].mean(),
            'avg_momentum': tier_rallies['momentum_score'].mean(),
            'avg_overall_score': tier_rallies['overall_score'].mean(),
            
            # Pre-rally conditions
            'avg_rsi_15m': tier_rallies['rsi_15m'].mean() if 'rsi_15m' in tier_rallies.columns else None,
            'avg_volume_rel': tier_rallies['volume_rel_15m'].mean() if 'volume_rel_15m' in tier_rallies.columns else None,
            
            # Multi-TF context
            'avg_trend_1h': tier_rallies['trend_soul_1h'].mean() if 'trend_soul_1h' in tier_rallies.columns else None,
            'avg_trend_4h': tier_rallies['trend_soul_4h'].mean() if 'trend_soul_4h' in tier_rallies.columns else None,
            
            # Time patterns
            'avg_bars_to_peak': tier_rallies['bars_to_peak'].mean(),
        }
    
    return analysis
