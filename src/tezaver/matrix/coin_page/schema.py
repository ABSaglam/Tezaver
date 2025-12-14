# Matrix V2 Coin Page Schema
"""
Schema definitions for Coin Strategy Pages.

V1 types (LEGACY): TimeframeProfile, TimeframeConfig, CoinStrategyPage
V2 types (CURRENT): CoinStrategyPageV2, MatrixStrategyProfileV2, etc.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# =============================================================================
# V1 TYPES (LEGACY) - Preserved for backward compatibility
# =============================================================================

@dataclass
class TimeframeProfile:
    """
    LEGACY: Represents a single profile within a timeframe configuration.
    
    Use MatrixStrategyProfileV2 for new development.
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
    LEGACY: Configuration for a single timeframe within a coin strategy page.
    
    Use TimeframeStrategiesV2 for new development.
    """
    profiles: list[TimeframeProfile] = field(default_factory=list)


@dataclass
class CoinStrategyPage:
    """
    LEGACY: Complete strategy page for a trading coin.
    
    Use CoinStrategyPageV2 for new development.
    """
    version: str
    symbol: str
    timeframes: dict[str, TimeframeConfig] = field(default_factory=dict)


# =============================================================================
# V2 TYPES (CURRENT) - CoinStrategyPageV2 and supporting types
# =============================================================================

@dataclass
class StrategyRuntimeMode:
    """
    Runtime mode settings for War Game / Live execution.
    
    Controls whether a profile is enabled for execution.
    Future: max_parallel_positions, allowed_environments, etc.
    """
    enabled: bool = True


@dataclass
class StrategyRiskContractV1:
    """
    Risk contract defining maximum risk allocation per trade.
    
    All Silver 15m profiles use uniform 1% risk cap.
    Coin-level adjustments planned for future versions.
    
    Attributes:
        profile_kind: Strategy profile category (e.g., "silver_15m")
        status: Approval status ("APPROVED" | "EXPERIMENTAL" | "DISABLED")
        max_risk_per_trade: Maximum risk per trade (0.01 = 1%)
        source: Data source version (e.g., "silver_15m_multi_coin_v1")
        notes: Human-readable notes about the contract
        reference: Reference metrics from benchmark (risk_ref, pnl_pct_ref, trades_ref)
    """
    profile_kind: str
    status: str
    max_risk_per_trade: float
    source: str
    notes: str
    reference: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyBenchmarkV1:
    """
    War Game benchmark results for a strategy profile.
    
    Captures performance metrics from War Game simulation.
    
    Attributes:
        capital_start: Starting capital (typically 100.0)
        capital_end: Ending capital after simulation
        pnl_pct: Total PnL percentage
        trades: Number of trades executed
    """
    capital_start: float
    capital_end: float
    pnl_pct: float
    trades: int


@dataclass
class StrategyConfigV1:
    """
    Complete strategy configuration from Coin Lab strategy card.
    
    Contains entry filters, ML filters, and exit parameters.
    
    Attributes:
        version: Strategy version (e.g., "v2_ml")
        entry_filters: RSI, volume, ATR, quality filters
        ml_filters: ML-derived filters (rsi_gap_1d, atr_pct_15m, rsi_1h)
        exit: Exit parameters (tp_pct, sl_pct, max_horizon_bars)
    """
    version: str
    entry_filters: Dict[str, Any] = field(default_factory=dict)
    ml_filters: Dict[str, Any] = field(default_factory=dict)
    exit: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MatrixStrategyProfileV2:
    """
    Complete strategy profile for a Matrix cell.
    
    Consolidates strategy config, benchmark, risk contract, and runtime mode.
    
    Attributes:
        profile_id: Unique identifier (e.g., "BTC_SILVER_15M_CORE_V1")
        kind: Profile category (e.g., "silver_15m_core")
        status: Approval status ("APPROVED" | "EXPERIMENTAL" | "DISABLED")
        strategy: Strategy configuration from Coin Lab
        benchmark_v1: Optional War Game benchmark results
        risk_contract_v1: Optional risk contract
        runtime_mode: Execution mode settings
    """
    profile_id: str
    kind: str
    status: str
    strategy: StrategyConfigV1
    benchmark_v1: Optional[StrategyBenchmarkV1] = None
    risk_contract_v1: Optional[StrategyRiskContractV1] = None
    runtime_mode: StrategyRuntimeMode = field(default_factory=StrategyRuntimeMode)


@dataclass
class TimeframeStrategiesV2:
    """
    Collection of strategy profiles for a single timeframe.
    
    Attributes:
        tf: Timeframe identifier (e.g., "15m", "1h", "4h")
        profiles: Dict of profile_id → MatrixStrategyProfileV2
    """
    tf: str
    profiles: Dict[str, MatrixStrategyProfileV2] = field(default_factory=dict)


@dataclass
class CoinStrategyPageV2:
    """
    Complete v2 strategy page for a trading coin.
    
    Single source of truth for all strategy profiles of a symbol.
    Contains strategy config, benchmark, risk contract, and runtime mode
    for each timeframe/profile combination.
    
    Attributes:
        version: Schema version (must be "matrix_coin_page_v2")
        symbol: Trading symbol (e.g., "BTCUSDT")
        timeframes: Dict of tf → TimeframeStrategiesV2
    """
    version: str
    symbol: str
    timeframes: Dict[str, TimeframeStrategiesV2] = field(default_factory=dict)

