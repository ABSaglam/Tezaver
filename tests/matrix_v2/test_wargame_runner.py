# Matrix V2 Wargame Runner Test
"""
Tests for Wargame runner and end-to-end pipeline.
"""

import pytest
from datetime import datetime


def test_wargame_imports():
    """Test that wargame modules can be imported."""
    from tezaver.matrix.wargame.scenarios import WargameScenario, build_demo_scenario
    from tezaver.matrix.wargame.runner import run_wargame
    from tezaver.matrix.wargame.reports import WargameReport
    
    assert WargameScenario is not None
    assert build_demo_scenario is not None
    assert run_wargame is not None
    assert WargameReport is not None


def test_build_demo_scenario():
    """Test building a demo scenario."""
    from tezaver.matrix.wargame.scenarios import build_demo_scenario
    
    scenario = build_demo_scenario()
    
    assert scenario.scenario_id == "DEMO_WARGAME_001"
    assert scenario.profile_id == "BTC_SILVER_15M_CORE_V1"
    assert scenario.symbol == "BTCUSDT"
    assert scenario.timeframe == "15m"
    assert scenario.initial_capital == 100.0
    assert isinstance(scenario.start_ts, datetime)
    assert isinstance(scenario.end_ts, datetime)
    assert scenario.end_ts > scenario.start_ts


def test_run_wargame_basic():
    """Test running a basic wargame simulation."""
    from tezaver.matrix.wargame.scenarios import build_demo_scenario
    from tezaver.matrix.wargame.runner import run_wargame
    
    scenario = build_demo_scenario()
    report = run_wargame(scenario)
    
    # Verify report structure
    assert report.scenario_id == scenario.scenario_id
    assert report.profile_id == scenario.profile_id
    assert report.capital_start == 100.0
    assert isinstance(report.capital_end, float)
    assert report.capital_end >= 0  # Capital should be non-negative
    assert report.trade_count >= 0
    assert 0.0 <= report.win_rate <= 1.0 or report.win_rate == 0.0
    assert report.max_drawdown >= 0.0


def test_run_wargame_with_custom_scenario():
    """Test running wargame with a custom scenario."""
    from tezaver.matrix.wargame.scenarios import WargameScenario
    from tezaver.matrix.wargame.runner import run_wargame
    
    scenario = WargameScenario(
        scenario_id="TEST_001",
        profile_id="TEST_PROFILE",
        symbol="BTCUSDT",
        timeframe="15m",
        start_ts=datetime(2024, 1, 1),
        end_ts=datetime(2024, 1, 2),
        initial_capital=500.0,
    )
    
    report = run_wargame(scenario)
    
    assert report.scenario_id == "TEST_001"
    assert report.profile_id == "TEST_PROFILE"
    assert report.capital_start == 500.0
    assert isinstance(report.capital_end, float)


def test_replay_datafeed():
    """Test ReplayDataFeed functionality."""
    from tezaver.matrix.wargame.replay_datafeed import ReplayDataFeed
    
    # Test from_dummy_data
    feed = ReplayDataFeed.from_dummy_data("BTCUSDT", "15m")
    
    assert feed.total_bars > 0
    assert feed.remaining_bars == feed.total_bars
    
    # Test getting bars
    bar1 = feed.get_next_bar("BTCUSDT", "15m")
    assert bar1 is not None
    assert "open" in bar1
    assert "high" in bar1
    assert "low" in bar1
    assert "close" in bar1
    assert "volume" in bar1
    
    # Test remaining bars decreased
    assert feed.remaining_bars == feed.total_bars - 1
    
    # Test reset
    feed.reset()
    assert feed.remaining_bars == feed.total_bars


def test_wargame_account_store():
    """Test WargameAccountStore functionality."""
    from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
    
    store = WargameAccountStore(initial_capital=200.0)
    
    # Test load creates new account
    account = store.load_account("test_profile")
    assert account.profile_id == "test_profile"
    assert account.capital == 200.0
    assert account.available_margin == 200.0
    assert len(account.positions) == 0
    
    # Test save and reload
    account.capital = 250.0
    store.save_account("test_profile", account)
    
    reloaded = store.load_account("test_profile")
    assert reloaded.capital == 250.0
