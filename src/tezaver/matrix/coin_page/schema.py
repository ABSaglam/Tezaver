# Matrix V2 Coin Page Schema
"""
Schema definitions for Coin Strategy Pages.
"""

from dataclasses import dataclass, field


@dataclass
class TimeframeProfile:
    """
    Represents a single profile within a timeframe configuration.
    """
    profile_id: str
    grade: str  # e.g., "diamond", "gold", "silver", "bronze"
    status: str  # "APPROVED" | "EXPERIMENTAL" | "DISABLED"
    strategy_card: str  # Path to strategy card JSON
    matrix_role: str  # "default" | "experimental" | "disabled"
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class TimeframeConfig:
    """
    Configuration for a single timeframe within a coin strategy page.
    """
    profiles: list[TimeframeProfile] = field(default_factory=list)


@dataclass
class CoinStrategyPage:
    """
    Complete strategy page for a trading coin.
    
    Defines all timeframes and their associated profiles for a symbol.
    """
    version: str
    symbol: str
    timeframes: dict[str, TimeframeConfig] = field(default_factory=dict)
