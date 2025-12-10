# Matrix V2 Core Imports Test
"""
Tests that all core modules can be imported correctly.
"""

import pytest


def test_core_types_import():
    """Test that core types can be imported."""
    from tezaver.matrix.core.types import (
        MarketSignal,
        TradeDecision,
        ExecutionReport,
        MatrixEventLogEntry,
    )
    assert MarketSignal is not None
    assert TradeDecision is not None
    assert ExecutionReport is not None
    assert MatrixEventLogEntry is not None


def test_core_account_import():
    """Test that core account types can be imported."""
    from tezaver.matrix.core.account import (
        Position,
        AccountState,
        AccountLedgerEntry,
        IAccountStore,
    )
    assert Position is not None
    assert AccountState is not None
    assert AccountLedgerEntry is not None
    assert IAccountStore is not None


def test_core_engine_import():
    """Test that core engine types can be imported."""
    from tezaver.matrix.core.engine import (
        IAnalyzer,
        IStrategist,
        IExecutor,
        UnifiedEngine,
    )
    assert IAnalyzer is not None
    assert IStrategist is not None
    assert IExecutor is not None
    assert UnifiedEngine is not None


def test_core_guardrail_import():
    """Test that guardrail types can be imported."""
    from tezaver.matrix.core.guardrail import (
        GuardrailConfig,
        GuardrailDecision,
        GuardrailController,
    )
    assert GuardrailConfig is not None
    assert GuardrailDecision is not None
    assert GuardrailController is not None


def test_core_profile_import():
    """Test that profile types can be imported."""
    from tezaver.matrix.core.profile import (
        MatrixCellProfile,
        MatrixProfileRepository,
    )
    assert MatrixCellProfile is not None
    assert MatrixProfileRepository is not None


def test_core_datafeed_import():
    """Test that datafeed protocol can be imported."""
    from tezaver.matrix.core.datafeed import IDataFeed
    assert IDataFeed is not None


def test_core_clock_import():
    """Test that clock protocol can be imported."""
    from tezaver.matrix.core.clock import IClock
    assert IClock is not None


def test_guardrail_config_instance():
    """Test creating a GuardrailConfig instance."""
    from tezaver.matrix.core.guardrail import GuardrailConfig
    
    config = GuardrailConfig(
        max_open_positions=5,
        max_daily_loss_pct=3.0,
        min_affinity_score=0.7,
    )
    assert config.max_open_positions == 5
    assert config.max_daily_loss_pct == 3.0
    assert config.min_affinity_score == 0.7


def test_matrix_cell_profile_instance():
    """Test creating a MatrixCellProfile instance."""
    from tezaver.matrix.core.profile import MatrixCellProfile
    
    profile = MatrixCellProfile(
        profile_id="btc_15m_silver_001",
        symbol="BTCUSDT",
        timeframe="15m",
        grade="silver",
        status="active",
        strategy_card_path="/path/to/card.json",
        matrix_role="trader",
    )
    assert profile.profile_id == "btc_15m_silver_001"
    assert profile.symbol == "BTCUSDT"
    assert profile.grade == "silver"
    assert profile.matrix_role == "trader"
