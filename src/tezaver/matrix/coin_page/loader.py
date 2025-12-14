# Matrix V2 Coin Page Loader
"""
Loader for Coin Strategy Page JSON files.

V1 loader (LEGACY): load_coin_strategy_page()
V2 loader (CURRENT): load_coin_strategy_page_v2()
"""

import json
from pathlib import Path
from typing import Any, Dict

from .schema import (
    # V1 types (LEGACY)
    TimeframeProfile,
    TimeframeConfig,
    CoinStrategyPage,
    # V2 types (CURRENT)
    CoinStrategyPageV2,
    TimeframeStrategiesV2,
    MatrixStrategyProfileV2,
    StrategyConfigV1,
    StrategyBenchmarkV1,
    StrategyRiskContractV1,
    StrategyRuntimeMode,
)


# =============================================================================
# V1 LOADER (LEGACY)
# =============================================================================

def load_coin_strategy_page(path: Path) -> CoinStrategyPage:
    """
    LEGACY: Load and validate a CoinStrategyPage (v1) from JSON.
    
    Use load_coin_strategy_page_v2() for new development.
    
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


# =============================================================================
# V2 LOADER (CURRENT)
# =============================================================================

def load_coin_strategy_page_v2(path: Path) -> CoinStrategyPageV2:
    """
    Load and validate a CoinStrategyPageV2 from JSON.
    
    Args:
        path: Path to the matrix_coin_page_v2.json file.
        
    Returns:
        Parsed CoinStrategyPageV2 object.
        
    Raises:
        FileNotFoundError: If path does not exist.
        ValueError: If version is wrong or required fields are missing.
    """
    if not path.exists():
        raise FileNotFoundError(f"matrix_coin_page_v2.json not found: {path}")
    
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Validate version
    version = data.get("version", "")
    if version != "matrix_coin_page_v2":
        raise ValueError(
            f"Unsupported coin page version: {version} (expected matrix_coin_page_v2)"
        )
    
    # Validate symbol
    symbol = data.get("symbol", "")
    if not symbol:
        raise ValueError("CoinStrategyPageV2: 'symbol' field is required and cannot be empty")
    
    # Validate timeframes exist
    raw_timeframes = data.get("timeframes", {})
    if not raw_timeframes:
        raise ValueError("CoinStrategyPageV2: 'timeframes' cannot be empty")
    
    # Parse timeframes
    timeframes: Dict[str, TimeframeStrategiesV2] = {}
    for tf_key, tf_data in raw_timeframes.items():
        raw_profiles = tf_data.get("profiles", {})
        if not raw_profiles:
            raise ValueError(
                f"CoinStrategyPageV2: timeframe '{tf_key}' must have at least one profile"
            )
        
        profiles: Dict[str, MatrixStrategyProfileV2] = {}
        for profile_id, p in raw_profiles.items():
            profiles[profile_id] = _parse_profile_v2(p)
        
        timeframes[tf_key] = TimeframeStrategiesV2(
            tf=tf_data.get("tf", tf_key),
            profiles=profiles,
        )
    
    return CoinStrategyPageV2(
        version=version,
        symbol=symbol,
        timeframes=timeframes,
    )


def _parse_profile_v2(data: Dict[str, Any]) -> MatrixStrategyProfileV2:
    """Parse a single MatrixStrategyProfileV2 from dict."""
    # Parse strategy config
    strategy_data = data.get("strategy", {})
    strategy = StrategyConfigV1(
        version=strategy_data.get("version", ""),
        entry_filters=strategy_data.get("entry_filters", {}),
        ml_filters=strategy_data.get("ml_filters", {}),
        exit=strategy_data.get("exit", {}),
    )
    
    # Parse optional benchmark
    benchmark_v1 = None
    if "benchmark_v1" in data and data["benchmark_v1"]:
        b = data["benchmark_v1"]
        benchmark_v1 = StrategyBenchmarkV1(
            capital_start=b.get("capital_start", 100.0),
            capital_end=b.get("capital_end", 100.0),
            pnl_pct=b.get("pnl_pct", 0.0),
            trades=b.get("trades", 0),
        )
    
    # Parse optional risk contract
    risk_contract_v1 = None
    if "risk_contract_v1" in data and data["risk_contract_v1"]:
        r = data["risk_contract_v1"]
        risk_contract_v1 = StrategyRiskContractV1(
            profile_kind=r.get("profile_kind", ""),
            status=r.get("status", "DISABLED"),
            max_risk_per_trade=r.get("max_risk_per_trade", 0.01),
            source=r.get("source", ""),
            notes=r.get("notes", ""),
            reference=r.get("reference", {}),
        )
    
    # Parse runtime mode
    runtime_data = data.get("runtime_mode", {})
    runtime_mode = StrategyRuntimeMode(
        enabled=runtime_data.get("enabled", True),
    )
    
    return MatrixStrategyProfileV2(
        profile_id=data.get("profile_id", ""),
        kind=data.get("kind", ""),
        status=data.get("status", "DISABLED"),
        strategy=strategy,
        benchmark_v1=benchmark_v1,
        risk_contract_v1=risk_contract_v1,
        runtime_mode=runtime_mode,
    )

