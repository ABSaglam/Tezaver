# Matrix V2 Coin Page Loader
"""
Loader for Coin Strategy Page JSON files.
"""

import json
from pathlib import Path

from .schema import TimeframeProfile, TimeframeConfig, CoinStrategyPage


def load_coin_strategy_page(path: Path) -> CoinStrategyPage:
    """
    Load and validate a CoinStrategyPage from JSON.
    
    Args:
        path: Path to the JSON file.
        
    Returns:
        Parsed CoinStrategyPage object.
        
    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If required fields are missing or invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Coin strategy page not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Validate version
    version = data.get("version", "")
    if not version:
        raise ValueError("CoinStrategyPage: 'version' field is required and cannot be empty")
    
    # Validate symbol
    symbol = data.get("symbol", "")
    if not symbol:
        raise ValueError("CoinStrategyPage: 'symbol' field is required and cannot be empty")
    
    # Validate timeframes exist
    raw_timeframes = data.get("timeframes", {})
    if not raw_timeframes:
        raise ValueError("CoinStrategyPage: 'timeframes' cannot be empty")
    
    # Parse timeframes
    timeframes: dict[str, TimeframeConfig] = {}
    for tf_key, tf_data in raw_timeframes.items():
        raw_profiles = tf_data.get("profiles", [])
        if not raw_profiles:
            raise ValueError(f"CoinStrategyPage: timeframe '{tf_key}' must have at least one profile")
        
        profiles: list[TimeframeProfile] = []
        for p in raw_profiles:
            profile = TimeframeProfile(
                profile_id=p.get("profile_id", ""),
                grade=p.get("grade", ""),
                status=p.get("status", "DISABLED"),
                strategy_card=p.get("strategy_card", ""),
                matrix_role=p.get("matrix_role", "default"),
                metadata=p.get("metadata", {}),
            )
            profiles.append(profile)
        timeframes[tf_key] = TimeframeConfig(profiles=profiles)
    
    return CoinStrategyPage(
        version=version,
        symbol=symbol,
        timeframes=timeframes,
    )
