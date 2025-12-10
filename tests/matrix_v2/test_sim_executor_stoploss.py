# Test SimExecutor Stop-Loss Logic
"""
Tests for stop-loss behavior in SimExecutor.
"""

import pytest
from pathlib import Path
from datetime import datetime
import uuid


def test_sim_executor_prefers_stop_when_dd_hits_sl():
    """Test that SL takes priority when drawdown exceeds SL threshold."""
    from tezaver.matrix.wargame.sim_executor import SimExecutor
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    from tezaver.matrix.core.types import TradeDecision
    from tezaver.matrix.core.account import AccountState
    
    store = WargameAccountStore(initial_capital=100.0)
    executor = SimExecutor(account_store=store)
    
    # Create a trade decision with 10% risk, 10% TP, 2% SL
    decision = TradeDecision(
        decision_id=str(uuid.uuid4()),
        signal_id="test_signal",
        symbol="BTCUSDT",
        timeframe="15m",
        action="open_long",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        position_size=10.0,  # 10% of 100 = 10
        reason="TEST",
        metadata={
            "tp_pct": 0.10,  # 10% TP
            "sl_pct": 0.02,  # 2% SL
        },
    )
    
    account = AccountState(
        profile_id="test",
        capital=100.0,
        available_margin=100.0,
        trade_count=0,
        positions=[],
    )
    
    # Gain is 8%, DD is -5% which exceeds SL of 2%, but gain < TP of 10%
    # Expectation: SL hit only, loss at -2%
    snapshot = {
        "future_max_gain_pct": 0.08,      # 8% potential gain (under 10% TP)
        "future_min_drawdown_pct": -0.05, # 5% drawdown (exceeds 2% SL)
    }
    
    report = executor.execute(decision, account, snapshot)
    
    # Position size = 10, SL = -2%, PnL = 10 * -0.02 = -0.2
    assert report.metadata["pnl"] == pytest.approx(-0.2, rel=1e-6)
    assert report.metadata["exit_reason"] == "stop_loss"
    assert store.get_equity() == pytest.approx(99.8, rel=1e-6)


def test_sim_executor_tp_when_no_sl_hit():
    """Test that TP is used when SL is not hit."""
    from tezaver.matrix.wargame.sim_executor import SimExecutor
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    from tezaver.matrix.core.types import TradeDecision
    from tezaver.matrix.core.account import AccountState
    
    store = WargameAccountStore(initial_capital=100.0)
    executor = SimExecutor(account_store=store)
    
    decision = TradeDecision(
        decision_id=str(uuid.uuid4()),
        signal_id="test_signal",
        symbol="BTCUSDT",
        timeframe="15m",
        action="open_long",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        position_size=10.0,
        reason="TEST",
        metadata={
            "tp_pct": 0.05,  # 5% TP
            "sl_pct": 0.02,  # 2% SL
        },
    )
    
    account = AccountState(
        profile_id="test",
        capital=100.0,
        available_margin=100.0,
        trade_count=0,
        positions=[],
    )
    
    # Gain is 10%, DD is only -1% (under SL of 2%)
    # Expectation: TP hit at 5%
    snapshot = {
        "future_max_gain_pct": 0.10,      # 10% gain (exceeds 5% TP)
        "future_min_drawdown_pct": -0.01, # 1% drawdown (under 2% SL)
    }
    
    report = executor.execute(decision, account, snapshot)
    
    # Position size = 10, TP = 5%, PnL = 10 * 0.05 = 0.5
    assert report.metadata["pnl"] == pytest.approx(0.5, rel=1e-6)
    assert report.metadata["exit_reason"] == "take_profit"
    assert store.get_equity() == pytest.approx(100.5, rel=1e-6)


def test_sim_executor_sl_priority_when_both_hit():
    """Test that SL takes priority when both TP and SL are hit."""
    from tezaver.matrix.wargame.sim_executor import SimExecutor
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    from tezaver.matrix.core.types import TradeDecision
    from tezaver.matrix.core.account import AccountState
    
    store = WargameAccountStore(initial_capital=100.0)
    executor = SimExecutor(account_store=store)
    
    decision = TradeDecision(
        decision_id=str(uuid.uuid4()),
        signal_id="test_signal",
        symbol="BTCUSDT",
        timeframe="15m",
        action="open_long",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        position_size=10.0,
        reason="TEST",
        metadata={
            "tp_pct": 0.05,  # 5% TP
            "sl_pct": 0.02,  # 2% SL
        },
    )
    
    account = AccountState(
        profile_id="test",
        capital=100.0,
        available_margin=100.0,
        trade_count=0,
        positions=[],
    )
    
    # Both TP and SL hit - SL should win (conservative)
    snapshot = {
        "future_max_gain_pct": 0.08,      # 8% gain (exceeds 5% TP)
        "future_min_drawdown_pct": -0.03, # 3% drawdown (exceeds 2% SL)
    }
    
    report = executor.execute(decision, account, snapshot)
    
    # SL priority: Position size = 10, SL = -2%, PnL = 10 * -0.02 = -0.2
    assert report.metadata["pnl"] == pytest.approx(-0.2, rel=1e-6)
    assert report.metadata["exit_reason"] == "stop_loss_priority"
    assert store.get_equity() == pytest.approx(99.8, rel=1e-6)


def test_sim_executor_horizon_when_neither_hit():
    """Test horizon exit when neither TP nor SL is hit."""
    from tezaver.matrix.wargame.sim_executor import SimExecutor
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    from tezaver.matrix.core.types import TradeDecision
    from tezaver.matrix.core.account import AccountState
    
    store = WargameAccountStore(initial_capital=100.0)
    executor = SimExecutor(account_store=store)
    
    decision = TradeDecision(
        decision_id=str(uuid.uuid4()),
        signal_id="test_signal",
        symbol="BTCUSDT",
        timeframe="15m",
        action="open_long",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        position_size=10.0,
        reason="TEST",
        metadata={
            "tp_pct": 0.10,  # 10% TP
            "sl_pct": 0.05,  # 5% SL
        },
    )
    
    account = AccountState(
        profile_id="test",
        capital=100.0,
        available_margin=100.0,
        trade_count=0,
        positions=[],
    )
    
    # Gain is 3%, DD is -2%, neither TP (10%) nor SL (5%) hit
    # Expectation: horizon exit at 3%
    snapshot = {
        "future_max_gain_pct": 0.03,      # 3% gain (under 10% TP)
        "future_min_drawdown_pct": -0.02, # 2% drawdown (under 5% SL)
    }
    
    report = executor.execute(decision, account, snapshot)
    
    # Position size = 10, horizon = 3%, PnL = 10 * 0.03 = 0.3
    assert report.metadata["pnl"] == pytest.approx(0.3, rel=1e-6)
    assert report.metadata["exit_reason"] == "horizon"
    assert store.get_equity() == pytest.approx(100.3, rel=1e-6)

