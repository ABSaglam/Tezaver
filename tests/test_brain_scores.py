"""
Test suite for brain_sync module.
Verifies that score computation produces values in expected ranges.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path
project_root = Path(__file__).resolve().parent.parent
src_path = project_root / "src"
if str(src_path) not in sys.path:
    sys.path.append(str(src_path))

from tezaver.core.brain_sync import compute_scores_from_wisdom


def test_compute_scores_range_with_mock_data(tmp_path, monkeypatch):
    """Test that compute_scores_from_wisdom produces scores in 0-100 range."""
    
    # Create fake wisdom data
    fake_pattern_stats = [
        {
            "trigger": "rsi_oversold",
            "timeframe": "1h",
            "sample_count": 50,
            "trust_score": 0.65,
            "avg_future_max_gain_pct": 5.2,
        },
        {
            "trigger": "macd_bull_cross",
            "timeframe": "4h",
            "sample_count": 30,
            "trust_score": 0.72,
            "avg_future_max_gain_pct": 8.1,
        },
    ]
    
    fake_trustworthy = [
        {"trigger": "rsi_oversold", "timeframe": "1h"},
        {"trigger": "macd_bull_cross", "timeframe": "4h"},
    ]
    
    fake_betrayal = []
    
    fake_vol_sig = {
        "avg_rel_volume": 1.2,
        "spike_frequency": 0.15,
    }
    
    # Mock the load_json_if_exists function to return our fake data
    def mock_load_json(path):
        path_str = str(path)
        if "pattern_stats.json" in path_str:
            return fake_pattern_stats
        elif "trustworthy_patterns.json" in path_str:
            return fake_trustworthy
        elif "betrayal_patterns.json" in path_str:
            return fake_betrayal
        elif "volatility_signature.json" in path_str:
            return fake_vol_sig
        return None
    
    # Apply the mock
    with patch("tezaver.core.brain_sync.load_json_if_exists", side_effect=mock_load_json):
        scores = compute_scores_from_wisdom("TESTCOIN", ["1h", "4h"])
    
    # Verify all scores are in 0-100 range
    score_fields = [
        "trend_soul_score",
        "harmony_score",
        "betrayal_score",
        "volume_trust",
        "opportunity_score",
        "self_trust_score",
    ]
    
    for field in score_fields:
        assert field in scores, f"Expected score field '{field}' not found"
        value = scores[field]
        assert 0 <= value <= 100, f"Score '{field}' = {value} is out of 0-100 range"


def test_compute_scores_with_empty_wisdom(monkeypatch):
    """Test that compute_scores_from_wisdom handles empty wisdom gracefully."""
    
    # Mock to return empty/null data
    def mock_load_json_empty(path):
        return None
    
    with patch("tezaver.core.brain_sync.load_json_if_exists", side_effect=mock_load_json_empty):
        scores = compute_scores_from_wisdom("EMPTYCOIN", ["1h"])
    
    # Scores should still be in valid range even with no data
    assert isinstance(scores, dict), "Expected scores to be a dictionary"
    
    # All scores should be 0 or low when there's no wisdom data
    for value in scores.values():
        if isinstance(value, (int, float)):
            assert 0 <= value <= 100, f"Score {value} is out of range with empty wisdom"
