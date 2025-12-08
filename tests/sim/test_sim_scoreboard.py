"""
Tests for Tezaver Sim v1.2 Scoreboard
"""
from unittest.mock import MagicMock, patch
import pandas as pd
import pytest

from tezaver.sim import sim_scoreboard
from tezaver.sim.sim_presets import SimPreset
from tezaver.sim.sim_config import RallySimConfig

# Mock Presets
@pytest.fixture
def mock_presets_list():
    p1 = SimPreset(
        id="P1", label_tr="P1 Label", description_tr="D1", timeframe="1h",
        base_config=RallySimConfig(symbol="UNK", timeframe="1h"),
        tags=[], version="1.0"
    )
    p2 = SimPreset(
        id="P2", label_tr="P2 Label", description_tr="D2", timeframe="1h",
        base_config=RallySimConfig(symbol="UNK", timeframe="1h"),
        tags=[], version="1.0"
    )
    return [p1, p2]

@patch('tezaver.sim.sim_presets.get_all_presets')
@patch('tezaver.sim.sim_engine.load_rally_events')
@patch('tezaver.sim.sim_engine.load_price_series')
@patch('tezaver.sim.sim_engine.simulate_trades')
@patch('tezaver.sim.sim_engine.summarize_results')
def test_run_preset_scoreboard_basic(
    mock_summary, mock_simulate, mock_prices, mock_events, mock_get_presets, 
    mock_presets_list
):
    # Setup Mocks
    mock_get_presets.return_value = mock_presets_list
    
    # Simulate valid data return
    mock_events.return_value = pd.DataFrame([{
        "event_time": "2023-01-01", 
        "rally_shape": "clean", 
        "quality_score": 80
    }])
    mock_prices.return_value = pd.DataFrame([{"close": 100}], index=pd.to_datetime(["2023-01-01"]))
    mock_simulate.return_value = (pd.DataFrame(), pd.DataFrame()) # Return empty trades for simplicity
    
    # Mock Summary returns
    mock_summary.side_effect = [
        {"num_trades": 10, "win_rate": 0.5, "total_pnl_pct": 0.1, "max_drawdown_pct": -0.05, "expectancy_R": 0.2},
        {"num_trades": 5, "win_rate": 0.8, "total_pnl_pct": 0.2, "max_drawdown_pct": -0.02, "expectancy_R": 0.5}
    ]
    
    scores, errors = sim_scoreboard.run_preset_scoreboard("BTCUSDT")
    
    assert len(scores) == 2
    assert len(errors) == 0
    
    s1 = scores[0]
    assert s1.preset_id == "P1"
    assert s1.num_trades == 10
    assert s1.net_pnl_pct == 0.1
    
    s2 = scores[1]
    assert s2.preset_id == "P2"
    assert s2.num_trades == 5
    
    # Verify Dataframe conversion
    df = sim_scoreboard.scores_to_dataframe(scores)
    assert len(df) == 2
    assert "net_pnl_pct" in df.columns

@patch('tezaver.sim.sim_presets.get_all_presets')
@patch('tezaver.sim.sim_engine.load_rally_events')
def test_run_preset_scoreboard_handles_errors(mock_events, mock_get_presets, mock_presets_list):
    """Ensure one failing preset doesn't crash the whole board."""
    mock_get_presets.return_value = mock_presets_list
    
    # P1 raises exception
    # P2 returns empty data (safe fail)
    
    def side_effect(symbol, tf):
        if tf == "1h": # P1 and P2 are same tf, need clearer distinction or mocking logic
           pass 
        return pd.DataFrame()

    # Let's mock filter_events instead to trigger different behavior or simulate_trades
    with patch('tezaver.sim.sim_engine.filter_events', side_effect=[Exception("Boom"), pd.DataFrame()]):
        # Mock valid load
        mock_events.return_value = pd.DataFrame([1]) 
        with patch('tezaver.sim.sim_engine.load_price_series', return_value=pd.DataFrame([1])):
             scores, errors = sim_scoreboard.run_preset_scoreboard("BTCUSDT")
             
             # P1 should fail
             # P2 should succeed (return 0 score due to empty filter)
             
             assert len(errors) == 1
             assert errors[0] == "P1"
             assert len(scores) == 1
             assert scores[0].preset_id == "P2"
