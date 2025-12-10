# Matrix V2 Silver Strategy Skeleton Test
"""
Tests for Silver strategy components.
"""

import pytest
from datetime import datetime
import tempfile
import json
from pathlib import Path


def test_silver_strategy_config_import():
    """Test that Silver strategy components can be imported."""
    from tezaver.matrix.strategies.silver_core import (
        SilverStrategyConfig,
        SilverAnalyzer,
        SilverStrategist,
        load_silver_strategy_config_from_card,
    )
    assert SilverStrategyConfig is not None
    assert SilverAnalyzer is not None
    assert SilverStrategist is not None
    assert load_silver_strategy_config_from_card is not None


def test_silver_strategy_config_instance():
    """Test creating a SilverStrategyConfig instance."""
    from tezaver.matrix.strategies.silver_core import SilverStrategyConfig
    
    cfg = SilverStrategyConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        rsi_range=(20.0, 30.0),
        volume_rel_range=(1.5, 3.0),
        atr_pct_range=(0.5, 2.0),
        min_quality_score=60.0,
        tp_pct=0.09,
        sl_pct=0.02,
        max_horizon_bars=48,
    )
    
    assert cfg.symbol == "BTCUSDT"
    assert cfg.timeframe == "15m"
    assert cfg.rsi_range == (20.0, 30.0)
    assert cfg.tp_pct == 0.09


def test_load_silver_strategy_config_from_card():
    """Test loading strategy config from JSON card."""
    from tezaver.matrix.strategies.silver_core import load_silver_strategy_config_from_card
    
    card_data = {
        "version": "v2_ml",
        "entry_filters": {
            "rsi_15m": {"min": 19.7, "max": 28.7},
            "volume_rel_15m": {"min": 2.0, "max": 2.4},
            "atr_pct_15m": {"min": 0.65, "max": 1.82},
            "quality_score": {"min": 60.0}
        },
        "ml_filters": {
            "rsi_gap_1d": {"min": -20.9, "max": 0.0},
            "atr_pct_15m": {"min": 0.71, "max": 1.82},
            "rsi_1h": {"min": 16.5, "max": 35.0}
        },
        "exit": {
            "tp_pct": 0.09,
            "sl_pct": 0.02,
            "max_horizon_bars": 48
        }
    }
    
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(card_data, f)
        temp_path = Path(f.name)
    
    try:
        cfg = load_silver_strategy_config_from_card(temp_path, "BTCUSDT", "15m")
        
        assert cfg.symbol == "BTCUSDT"
        assert cfg.timeframe == "15m"
        assert cfg.rsi_range == (19.7, 28.7)
        assert cfg.volume_rel_range == (2.0, 2.4)
        assert cfg.atr_pct_range == (0.65, 1.82)
        assert cfg.min_quality_score == 60.0
        assert cfg.tp_pct == 0.09
        assert cfg.sl_pct == 0.02
        assert cfg.max_horizon_bars == 48
        assert cfg.rsi_gap_1d_range == (-20.9, 0.0)
        assert cfg.metadata["card_version"] == "v2_ml"
    finally:
        temp_path.unlink()


def test_silver_analyzer_signal_in_range():
    """Test SilverAnalyzer generates signal when indicators are in range."""
    from tezaver.matrix.strategies.silver_core import SilverStrategyConfig, SilverAnalyzer
    
    cfg = SilverStrategyConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        rsi_range=(20.0, 30.0),
    )
    
    analyzer = SilverAnalyzer(cfg)
    
    # RSI in range -> should generate signal
    snapshot = {"rsi_15m": 25.0, "timestamp": datetime.now()}
    signals = analyzer.analyze(snapshot)
    
    assert len(signals) == 1
    assert signals[0].signal_type == "SILVER_ENTRY"
    assert signals[0].symbol == "BTCUSDT"


def test_silver_analyzer_no_signal_out_of_range():
    """Test SilverAnalyzer doesn't generate signal when indicators out of range."""
    from tezaver.matrix.strategies.silver_core import SilverStrategyConfig, SilverAnalyzer
    
    cfg = SilverStrategyConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        rsi_range=(20.0, 30.0),
    )
    
    analyzer = SilverAnalyzer(cfg)
    
    # RSI out of range -> no signal
    snapshot = {"rsi_15m": 50.0, "timestamp": datetime.now()}
    signals = analyzer.analyze(snapshot)
    
    assert len(signals) == 0


def test_silver_strategist_creates_decision():
    """Test SilverStrategist creates decision for SILVER_ENTRY signal."""
    from tezaver.matrix.strategies.silver_core import SilverStrategyConfig, SilverStrategist
    from tezaver.matrix.core.types import MarketSignal
    from tezaver.matrix.core.account import AccountState
    
    cfg = SilverStrategyConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        tp_pct=0.09,
        sl_pct=0.02,
    )
    
    strategist = SilverStrategist(cfg, risk_per_trade_pct=2.0)
    
    signal = MarketSignal(
        signal_id="test_signal",
        symbol="BTCUSDT",
        timeframe="15m",
        signal_type="SILVER_ENTRY",
        direction="long",
        confidence=1.0,
        timestamp=datetime.now(),
    )
    
    account = AccountState(
        profile_id="test",
        capital=1000.0,
        available_margin=1000.0,
    )
    
    decision = strategist.evaluate(signal, account)
    
    assert decision is not None
    assert decision.action == "open_long"
    assert decision.symbol == "BTCUSDT"
    assert decision.position_size == 20.0  # 2% of 1000
    assert decision.metadata["tp_pct"] == 0.09


def test_silver_strategist_ignores_other_signals():
    """Test SilverStrategist returns None for non-SILVER_ENTRY signals."""
    from tezaver.matrix.strategies.silver_core import SilverStrategyConfig, SilverStrategist
    from tezaver.matrix.core.types import MarketSignal
    from tezaver.matrix.core.account import AccountState
    
    cfg = SilverStrategyConfig(symbol="BTCUSDT", timeframe="15m")
    strategist = SilverStrategist(cfg)
    
    signal = MarketSignal(
        signal_id="test",
        symbol="BTCUSDT",
        timeframe="15m",
        signal_type="NOOP",
        direction="neutral",
        confidence=0.0,
        timestamp=datetime.now(),
    )
    
    account = AccountState(
        profile_id="test",
        capital=1000.0,
        available_margin=1000.0,
    )
    
    decision = strategist.evaluate(signal, account)
    assert decision is None


def test_wargame_with_silver_profile():
    """Test wargame runs with Silver profile using SilverAnalyzer."""
    from tezaver.matrix.wargame.scenarios import WargameScenario
    from tezaver.matrix.wargame.runner import run_wargame
    
    scenario = WargameScenario(
        scenario_id="SILVER_TEST_001",
        profile_id="BTC_SILVER_15M_CORE_V1",
        symbol="BTCUSDT",
        timeframe="15m",
        start_ts=datetime(2024, 1, 1),
        end_ts=datetime(2024, 1, 2),
        initial_capital=100.0,
    )
    
    report = run_wargame(scenario)
    
    assert report.scenario_id == "SILVER_TEST_001"
    assert report.profile_id == "BTC_SILVER_15M_CORE_V1"
    assert report.capital_start == 100.0
    assert isinstance(report.capital_end, float)
