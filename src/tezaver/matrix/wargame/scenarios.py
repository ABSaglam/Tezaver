# Matrix V2 Wargame Scenarios
"""
Scenario definitions for wargame simulations.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class WargameScenario:
    """
    Defines a wargame simulation scenario.
    
    Specifies the profile, symbol, timeframe, and time range for simulation.
    """
    scenario_id: str
    profile_id: str
    symbol: str
    timeframe: str
    start_ts: datetime
    end_ts: datetime
    initial_capital: float = 100.0
    risk_per_trade_pct: float = 0.01  # 0.01 = %1 (requested risk)
    max_risk_per_trade: float | None = None  # Risk cap from risk_contract_v1
    mode: str = "contract"  # "contract" = enforce cap, "experiment" = bypass cap


def build_demo_scenario() -> WargameScenario:
    """
    Temporary demo scenario for BTCUSDT 15m Silver core profile.
    
    In the future, this will be configured via YAML/JSON.
    
    Returns:
        WargameScenario for testing the pipeline.
    """
    return WargameScenario(
        scenario_id="DEMO_WARGAME_001",
        profile_id="BTC_SILVER_15M_CORE_V1",
        symbol="BTCUSDT",
        timeframe="15m",
        start_ts=datetime(2024, 1, 1, 0, 0, 0),
        end_ts=datetime(2024, 1, 31, 23, 59, 59),
        initial_capital=100.0,
        risk_per_trade_pct=0.01,
    )


def build_btc_silver_15m_patterns_scenario(
    risk_per_trade_pct: float = 0.01,
) -> WargameScenario:
    """
    BTCUSDT Silver 15m core profil için rally_patterns_v1 üzerinden
    War Game senaryosu.
    
    100 başlangıç sermayesi ile gerçek pattern data'sını test eder.
    
    Args:
        risk_per_trade_pct: Risk per trade (0.01 = 1%, 1.0 = 100%).
    
    Returns:
        WargameScenario for BTC Silver 15m patterns.
    """
    return WargameScenario(
        scenario_id="BTC_SILVER_15M_PATTERNS_V1",
        profile_id="BTC_SILVER_15M_CORE_V1",
        symbol="BTCUSDT",
        timeframe="15m",
        start_ts=datetime(2023, 12, 1, 0, 0, 0),
        end_ts=datetime(2024, 12, 31, 23, 59, 59),
        initial_capital=100.0,
        risk_per_trade_pct=risk_per_trade_pct,
    )


def build_silver_15m_patterns_scenario(
    symbol: str,
    risk_per_trade_pct: float = 0.01,
) -> WargameScenario:
    """
    Generic Silver 15m War Game scenario for any symbol.
    
    Works with BTC, ETH, SOL, etc.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT", "ETHUSDT", "SOLUSDT").
        risk_per_trade_pct: Risk per trade (0.01 = 1%, 1.0 = 100%).
    
    Returns:
        WargameScenario for the given symbol's Silver 15m patterns.
    """
    # Remove 'USDT' suffix for profile ID if present
    base_symbol = symbol.replace("USDT", "")
    
    return WargameScenario(
        scenario_id=f"{base_symbol}_SILVER_15M_PATTERNS_V1",
        profile_id=f"{base_symbol}_SILVER_15M_CORE_V1",
        symbol=symbol,
        timeframe="15m",
        start_ts=datetime(2023, 12, 1, 0, 0, 0),
        end_ts=datetime(2024, 12, 31, 23, 59, 59),
        initial_capital=100.0,
        risk_per_trade_pct=risk_per_trade_pct,
    )

