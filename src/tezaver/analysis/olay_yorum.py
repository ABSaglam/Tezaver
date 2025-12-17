"""
Olay/Yorum Analysis Module

Provides deterministic heuristics to calculate "Ahenk" (Harmony) and "Betrayal" (Risk)
scores for Rally events.
"""

from typing import Dict, Any, Tuple

def calculate_ahenk_score(details: Dict[str, Any]) -> Tuple[float, str]:
    """
    Calculate Ahenk (Harmony) score [0..1].
    
    Ahenk represents the quality/confluence of the rally setup.
    Higher score = better alignment (RSI not overbought, reasonable ATR).
    
    Heuristic:
    - Base: 0.5
    - RSI: +0.2 if 40 < RSI < 70 (Sweet spot)
    - ATR: +0.2 if ATR > 0.5% (Volatility present)
    - Vol: +0.1 if Volume > Avg (if available, else 0)
    """
    score = 0.5
    reason_parts = []
    
    # RSI Component
    rsi = float(details.get("trigger_rsi", 0.0))
    if 40 < rsi < 70:
        score += 0.2
        reason_parts.append("RSI_OK")
    elif rsi >= 70:
        score -= 0.1
        reason_parts.append("RSI_HOT")
        
    # ATR Component
    atr = float(details.get("trigger_atr_pct", 0.0))
    if atr > 0.5:
        score += 0.2
        reason_parts.append("ATR_ACTIVE")
        
    # Clip
    score = max(0.0, min(1.0, score))
    
    return score, "|".join(reason_parts) if reason_parts else "NEUTRAL"


def calculate_betrayal_risk(details: Dict[str, Any]) -> Tuple[float, str]:
    """
    Calculate Betrayal (Reversion Risk) score [0..1].
    
    Betrayal represents how much the rally retraced/failed after detection.
    
    Heuristic:
    - Risk = abs(future_min_pct) / (future_max_gain_pct + 0.001)
    - If min_pct is significantly negative compared to gain, risk is high.
    """
    min_pct = float(details.get("future_min_pct", 0.0)) # Usually negative for drawdown
    max_gain = float(details.get("future_max_gain_pct", 0.0))
    
    if max_gain < 0.01: # No gain, pure risk if any drawdown
        risk = 1.0 if min_pct < -0.01 else 0.0
        return risk, "NO_GAIN"
        
    drawdown = abs(min_pct)
    risk_ratio = drawdown / max_gain
    
    score = min(1.0, risk_ratio)
    
    reason = "STABLE"
    if score > 0.8: reason = "BETRAYED"
    elif score > 0.5: reason = "SHAKY"
    elif score > 0.2: reason = "NORMAL_PULLBACK"
    
    return score, reason
