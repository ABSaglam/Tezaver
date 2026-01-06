"""
Tier Utilities
Shared logic for Rally Tier normalization and computation.
Extracted to avoid circular imports between UI and Assembler.
"""
from typing import Any, Optional
import pandas as pd
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct

# Tier constants
TIERS = ["DIAMOND", "GOLD", "SILVER", "BRONZE", "IRON"]

# Rally bucket to tier mapping
BUCKET_TO_TIER = {
    '30p_plus': 'DIAMOND',
    '20p_30p': 'GOLD',
    '10p_20p': 'SILVER',
    '5p_10p': 'BRONZE',
    '0p_5p': 'IRON',
}

def normalize_tier(value: Any) -> Optional[str]:
    """
    Normalize tier/grade string to standard tier name.
    
    Args:
        value: Tier string (can be 'diamond', 'DIAMOND', 'DIA', etc.) or None
    
    Returns:
        Standardized tier name ("DIAMOND", "GOLD", "SILVER", "BRONZE") or None if unknown
    """
    if pd.isna(value) or value is None:
        return None
    
    s = str(value).strip().upper()
    
    # Diamond variants
    if s in ["DIAMOND", "DIA", "💎"]:
        return "DIAMOND"
    
    # Gold variants
    if s in ["GOLD", "GLD", "🥇"]:
        return "GOLD"
    
    # Silver variants
    if s in ["SILVER", "SLV", "🥈"]:
        return "SILVER"
    
    # Bronze variants
    if s in ["BRONZE", "BRZ", "🥉"]:
        return "BRONZE"
    
    # Iron variants
    if s in ["IRON", "IRN", "DEMIR", "🔩"]:
        return "IRON"
    
    return None

def compute_tier_from_gain(gain_pct: float) -> Optional[str]:
    """
    Compute tier from future_max_gain_pct.
    WRAPPER: This function now delegates to the canonical implementation
    in rally_grade_cards.py to prevent threshold drift.
    
    Args:
        gain_pct: Gain percentage as decimal (e.g., 0.30 for 30%)
    
    Returns:
        Tier name or None if gain is too low
    """
    return compute_tier_from_gain_pct(gain_pct)
