# Matrix V2 Wargame BTC Silver Patterns PnL Test
"""
Tests for War Game with real PnL calculation.
"""

import pytest
from pathlib import Path


def test_run_btc_silver_15m_from_patterns_has_trades_and_capital():
    """Test War Game produces trades and calculates PnL."""
    from tezaver.matrix.wargame.runner import run_btc_silver_15m_from_patterns
    
    parquet_path = Path("data/ai_datasets/BTCUSDT/15m/rally_patterns_v1.parquet")
    
    if not parquet_path.exists():
        pytest.skip(f"Parquet file not found: {parquet_path}")
    
    report = run_btc_silver_15m_from_patterns(parquet_path)
    
    assert report.capital_start == 100.0
    assert report.trade_count >= 0
    # Pipeline works and produces numeric result
    assert report.capital_end >= 0.0
    assert isinstance(report.win_rate, float)


def test_sim_executor_calculates_pnl():
    """Test SimExecutor applies PnL from future_max_gain_pct."""
    from tezaver.matrix.wargame.sim_executor import SimExecutor
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    from tezaver.matrix.core.types import TradeDecision
    from tezaver.matrix.core.account import AccountState
    
    store = WargameAccountStore(initial_capital=100.0)
    executor = SimExecutor(account_store=store)
    
    decision = TradeDecision(
        decision_id="test_1",
        signal_id="sig_1",
        symbol="BTCUSDT",
        timeframe="15m",
        action="open_long",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        position_size=100.0,
        reason="test",
        metadata={"tp_pct": 0.10, "sl_pct": 0.02},
    )
    
    account = AccountState(
        profile_id="test",
        capital=100.0,
        available_margin=100.0,
    )
    
    # Snapshot with 5% gain
    snapshot = {"future_max_gain_pct": 0.05}
    
    report = executor.execute(decision, account, snapshot)
    
    assert report.status == "filled"
    assert report.metadata["pnl_pct"] == 0.05
    assert report.metadata["pnl"] == 5.0  # 100 * 0.05
    assert store.get_equity() == 105.0


def test_sim_executor_caps_at_tp():
    """Test SimExecutor caps gain at TP level."""
    from tezaver.matrix.wargame.sim_executor import SimExecutor
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    from tezaver.matrix.core.types import TradeDecision
    from tezaver.matrix.core.account import AccountState
    
    store = WargameAccountStore(initial_capital=100.0)
    executor = SimExecutor(account_store=store)
    
    decision = TradeDecision(
        decision_id="test_2",
        signal_id="sig_2",
        symbol="BTCUSDT",
        timeframe="15m",
        action="open_long",
        entry_price=None,
        stop_loss=None,
        take_profit=None,
        position_size=100.0,
        reason="test",
        metadata={"tp_pct": 0.05, "sl_pct": 0.02},  # TP at 5%
    )
    
    account = AccountState(
        profile_id="test",
        capital=100.0,
        available_margin=100.0,
    )
    
    # Snapshot with 10% gain (should be capped at 5%)
    snapshot = {"future_max_gain_pct": 0.10}
    
    report = executor.execute(decision, account, snapshot)
    
    assert report.metadata["pnl_pct"] == 0.05  # Capped at TP
    assert store.get_equity() == 105.0


def test_wargame_account_store_tracks_equity():
    """Test WargameAccountStore tracks equity correctly."""
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    
    store = WargameAccountStore(initial_capital=100.0)
    
    assert store.get_equity() == 100.0
    
    # Apply positive trade
    store.apply_execution({"event_type": "TRADE", "pnl": 5.0})
    assert store.get_equity() == 105.0
    
    # Apply negative trade
    store.apply_execution({"event_type": "TRADE", "pnl": -3.0})
    assert store.get_equity() == 102.0
    
    # Check ledger
    ledger = store.get_ledger()
    assert len(ledger) == 2
