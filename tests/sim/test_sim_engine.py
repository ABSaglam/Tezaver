"""
Tests for Tezaver Sim v1 Engine
"""
import pandas as pd
import pytest
from datetime import datetime, timedelta

from tezaver.sim.sim_config import RallySimConfig
from tezaver.sim import sim_engine

@pytest.fixture
def mock_prices():
    """Create a mock price series."""
    start = datetime(2023, 1, 1, 10, 0)
    periods = 100
    timestamps = [start + timedelta(hours=i) for i in range(periods)]
    
    # Flat price initially
    data = {
        'open': [100.0] * periods,
        'high': [100.0] * periods,
        'low': [100.0] * periods,
        'close': [100.0] * periods
    }
    df = pd.DataFrame(data, index=timestamps)
    df.index.name = 'timestamp'
    return df

@pytest.fixture
def mock_event(mock_prices):
    """Create a mock rally event."""
    return pd.DataFrame([{
        'event_time': mock_prices.index[10],
        'event_index': 10,
        'future_max_gain_pct': 0.10,
        'quality_score': 80.0,
        'rally_shape': 'clean',
        'rally_bucket': '10p_20p'
    }])

def test_take_profit(mock_prices, mock_event):
    """Test TP execution."""
    # Modify price to hit TP
    # Entry at index 10 (price 100). TP 5% = 105.
    # Set high at index 15 to 106.
    mock_prices.iloc[15, mock_prices.columns.get_loc('high')] = 106.0
    mock_prices.iloc[15, mock_prices.columns.get_loc('close')] = 106.0
    
    cfg = RallySimConfig(
        symbol="TEST",
        timeframe="1h",
        tp_pct=0.05,
        sl_pct=0.02,
        initial_equity=10000.0
    )
    
    trades, equity = sim_engine.simulate_trades(mock_event, mock_prices, cfg)
    
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t['exit_reason'] == 'TP'
    assert t['exit_price'] == 105.0 # Should execute exactly at TP
    assert t['pnl'] > 0

def test_stop_loss(mock_prices, mock_event):
    """Test SL execution."""
    # Entry at 100. SL 2% = 98.
    # Set low at index 12 to 97.
    mock_prices.iloc[12, mock_prices.columns.get_loc('low')] = 97.0
    mock_prices.iloc[12, mock_prices.columns.get_loc('close')] = 97.0
    
    cfg = RallySimConfig(
        symbol="TEST",
        timeframe="1h",
        tp_pct=0.05,
        sl_pct=0.02,
        initial_equity=10000.0
    )
    
    trades, equity = sim_engine.simulate_trades(mock_event, mock_prices, cfg)
    
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t['exit_reason'] == 'SL'
    assert t['exit_price'] == 98.0 # Exec at SL
    assert t['pnl'] < 0

def test_timeout(mock_prices, mock_event):
    """Test Timeout."""
    # Price stays flat at 100.
    # Horizon 5 bars.
    
    cfg = RallySimConfig(
        symbol="TEST",
        timeframe="1h",
        max_horizon_bars=5,
        tp_pct=0.05,
        sl_pct=0.02
    )
    
    trades, equity = sim_engine.simulate_trades(mock_event, mock_prices, cfg)
    
    assert len(trades) == 1
    t = trades.iloc[0]
    assert t['exit_reason'] == 'TIMEOUT'
    # Exit at close of index 10 + 5 = 15?
    # Logic: future_prices = prices.loc[entry:].iloc[1 : horizon+1]
    # Length of future slices is 5.
    # Last one is the exit.
    assert t['exit_price'] == 100.0
    assert t['gross_return_pct'] == 0.0

def test_summary_metrics(mock_prices, mock_event):
    """Test summary generation."""
    # Force a win
    mock_prices.iloc[15, mock_prices.columns.get_loc('high')] = 110.0
    
    cfg = RallySimConfig(symbol="TEST", timeframe="1h")
    trades, equity = sim_engine.simulate_trades(mock_event, mock_prices, cfg)
    
    summary = sim_engine.summarize_results(trades, equity)
    
    assert summary['num_trades'] == 1
    assert summary['win_rate'] == 1.0
    assert summary['final_equity'] > 10000.0
