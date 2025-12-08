"""
Tests for Tezaver Sim v1.3 Affinity Export
"""
import pytest
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

from tezaver.sim import sim_affinity
from tezaver.sim.sim_scoreboard import PresetScore

def test_compute_preset_affinity_scoring_logic():
    cfg = sim_affinity.AffinityConfig()
    
    # 1. Excellent Stats
    score_good = PresetScore(
        preset_id="GOOD", preset_label_tr="G", timeframe="1h",
        num_trades=30, win_rate=0.75, net_pnl_pct=0.5,
        max_drawdown_pct=-0.15, expectancy_pct=1.8, avg_hold_bars=10
    )
    aff_good = sim_affinity.compute_preset_affinity(score_good, cfg)
    
    assert aff_good.affinity_score > 80
    assert aff_good.status == "reliable"
    assert "A" in aff_good.affinity_grade
    
    # 2. Bad Stats
    score_bad = PresetScore(
        preset_id="BAD", preset_label_tr="B", timeframe="1h",
        num_trades=30, win_rate=0.20, net_pnl_pct=-0.1,
        max_drawdown_pct=-0.50, expectancy_pct=-0.5, avg_hold_bars=10
    )
    aff_bad = sim_affinity.compute_preset_affinity(score_bad, cfg)
    
    assert aff_bad.affinity_score < 40
    assert aff_bad.status == "reliable" # enough data, just bad
    assert aff_bad.net_pnl_pct == -0.1
    
    # 3. Low Data
    score_low = PresetScore(
        preset_id="LOW", preset_label_tr="L", timeframe="1h",
        num_trades=3, win_rate=1.0, net_pnl_pct=0.1,
        max_drawdown_pct=0.0, expectancy_pct=2.0, avg_hold_bars=10
    )
    aff_low = sim_affinity.compute_preset_affinity(score_low, cfg)
    
    assert aff_low.status == "low_data"
    # Even with perfect stats, score should be penalized for count
    # 100 raw -> 0.5 penalty -> 50 score
    assert aff_low.affinity_score <= 60 

def test_compute_strategy_affinity_selection():
    p1 = PresetScore("P1", "P1", "1h", 20, 0.6, 0.2, -0.2, 1.0, 10) # Good Reliable
    p2 = PresetScore("P2", "P2", "4h", 20, 0.4, 0.0, -0.4, 0.0, 10) # Mediocre Reliable
    p3 = PresetScore("P3", "P3", "15m", 2, 1.0, 0.5, 0.0, 5.0, 10) # Amazing but Low Data
    
    summary = sim_affinity.compute_strategy_affinity([p1, p2, p3], "BTC")
    
    # Should pick P1 as best reliable
    assert summary.best_overall is not None
    assert summary.best_overall.preset_id == "P1"
    assert summary.best_overall.status == "reliable"
    
    # TR Summary check
    assert "P1" in summary.summary_tr
    assert "Skor" in summary.summary_tr

def test_save_strategy_affinity(tmp_path):
    # Mock get_coin_profile_dir to return tmp_path
    with patch("tezaver.sim.sim_affinity.get_coin_profile_dir", return_value=tmp_path):
        summary = sim_affinity.StrategyAffinitySummary(
            symbol="TEST", base_equity=10000, presets={}, best_overall=None
        )
        out_file = sim_affinity.save_strategy_affinity("TEST", summary)
        
        assert out_file.exists()
        with open(out_file) as f:
            data = json.load(f)
            assert data['symbol'] == "TEST"
            assert "meta" in data
