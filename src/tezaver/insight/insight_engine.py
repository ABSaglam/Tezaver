
"""
Tezaver Insight Engine (M25)
============================

Aggregates data from multiple sources (Rally Radar, Sim Promotion, Time-Labs)
to provide a centralized high-level market overview.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from tezaver.core.coin_cell_paths import get_project_root
from tezaver.core.config import DEFAULT_COINS

logger = logging.getLogger("InsightEngine")

@dataclass
class CoinInsight:
    symbol: str
    radar_status: str = "NO_DATA"
    radar_score: float = 0.0
    dominant_lane: str = "-"
    approved_strategies: List[str] = field(default_factory=list)
    candidate_strategies: List[str] = field(default_factory=list)
    last_update: str = "-"
    
    # Pre-calculated emoji representation
    radar_emoji: str = "⚪" 
    
    def __post_init__(self):
        # Map radar status to emoji
        emoji_map = {
            "HOT": "🔥",
            "NEUTRAL": "😐",
            "COLD": "❄️",
            "CHAOTIC": "🌀",
            "NO_DATA": "⚪"
        }
        self.radar_emoji = emoji_map.get(self.radar_status, "⚪")

def load_market_overview(coins: Optional[List[str]] = None) -> pd.DataFrame:
    """
    Scans all (or specified) coins and builds a consolidated market overview dataframe.
    """
    if not coins:
        # Fallback to scanning directory if no list provided, or use registered
        coins = _scan_profile_dirs()
        if not coins:
             coins = DEFAULT_COINS
    
    insights = []
    
    for symbol in coins:
        try:
            insight = _build_coin_insight(symbol)
            if insight:
                insights.append(insight)
        except Exception as e:
            logger.warning(f"Failed to build insight for {symbol}: {e}")
            
    if not insights:
        return pd.DataFrame()
        
    # Convert to DataFrame
    data = [
        {
            "Symbol": i.symbol,
            "Radar": f"{i.radar_emoji} {i.radar_status}",
            "Score": i.radar_score,
            "Lane": i.dominant_lane,
            "Approved": ", ".join(i.approved_strategies) if i.approved_strategies else "-",
            "Candidates": ", ".join(i.candidate_strategies) if i.candidate_strategies else "-",
            "Last Update": i.last_update
        }
        for i in insights
    ]
    
    df = pd.DataFrame(data)
    
    # Sort by score desc by default
    if "Score" in df.columns:
        df = df.sort_values("Score", ascending=False)
        
    return df

def _scan_profile_dirs() -> List[str]:
    """List valid coin directories in data/coin_profiles."""
    root = get_project_root() / "data" / "coin_profiles"
    if not root.exists():
        return []
    
    return [d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")]

def _build_coin_insight(symbol: str) -> Optional[CoinInsight]:
    """Load profile JSONs and construct CoinInsight object."""
    root = get_project_root() / "data" / "coin_profiles" / symbol
    if not root.exists():
        return None
    
    # 1. Load Rally Radar
    radar_path = root / "rally_radar.json"
    radar_data = {}
    if radar_path.exists():
        try:
            with open(radar_path, "r", encoding="utf-8") as f:
                radar_data = json.load(f)
        except Exception:
            pass
            
    # 2. Load Sim Promotion
    promo_path = root / "sim_promotion.json"
    promo_data = {}
    if promo_path.exists():
        try:
            with open(promo_path, "r", encoding="utf-8") as f:
                promo_data = json.load(f)
        except Exception:
            pass
            
    # Extract Metrics
    
    # Radar
    overall = radar_data.get("overall", {})
    r_status = overall.get("overall_status", "NO_DATA")
    dom_lane = overall.get("dominant_lane", "-")
    
    # Calculate an aggregate score (e.g. max of timeframe scores or avg)
    # Let's take 4h score as primary proxy for "Score" column, or average if multiple
    tfs = radar_data.get("timeframes", {})
    scores = []
    for tf in ["15m", "1h", "4h"]:
        if tf in tfs:
            scores.append(tfs[tf].get("environment_score", 0.0))
            
    r_score = max(scores) if scores else 0.0
    
    # Promotion
    approved = []
    candidate = []
    strategies = promo_data.get("strategies", {})
    for pid, s in strategies.items():
        st = s.get("status")
        if st == "APPROVED":
            approved.append(pid)
        elif st == "CANDIDATE":
            candidate.append(pid)
            
    # Time
    generated_at = radar_data.get("generated_at", "-")
    # Simplify time string
    if "T" in generated_at:
        generated_at = generated_at.split("T")[1][:5] # HH:MM
            
    return CoinInsight(
        symbol=symbol,
        radar_status=r_status,
        radar_score=r_score,
        dominant_lane=dom_lane,
        approved_strategies=approved,
        candidate_strategies=candidate,
        last_update=generated_at
    )
