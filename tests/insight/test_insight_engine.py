
"""
Tests for Tezaver Insight Engine (M25)
"""
import pytest
import json
import logging
import pandas as pd
from unittest.mock import MagicMock, patch
from pathlib import Path

from tezaver.insight.insight_engine import (
    load_market_overview,
    CoinInsight,
    _build_coin_insight
)

# Mock Data
MOCK_RADAR = {
    "overall": {
        "overall_status": "HOT",
        "dominant_lane": "1h"
    },
    "timeframes": {
        "15m": {"environment_score": 50.0},
        "1h": {"environment_score": 85.0},
        "4h": {"environment_score": 60.0}
    },
    "generated_at": "2025-12-06T12:00:00"
}

MOCK_PROMO = {
    "strategies": {
        "STRAT_A": {"status": "APPROVED"},
        "STRAT_B": {"status": "CANDIDATE"},
        "STRAT_C": {"status": "REJECTED"}
    }
}

@pytest.fixture
def mock_root(tmp_path):
    """Setup a mock file system for data/coin_profiles."""
    
    # Mock project root structure
    data_dir = tmp_path / "data" / "coin_profiles"
    data_dir.mkdir(parents=True)
    
    # Coin A: Full data
    coin_a = data_dir / "COIN_A"
    coin_a.mkdir()
    (coin_a / "rally_radar.json").write_text(json.dumps(MOCK_RADAR))
    (coin_a / "sim_promotion.json").write_text(json.dumps(MOCK_PROMO))
    
    # Coin B: No data
    coin_b = data_dir / "COIN_B"
    coin_b.mkdir()
    
    # Patch get_project_root to return tmp_path
    with patch("tezaver.insight.insight_engine.get_project_root", return_value=tmp_path):
        yield tmp_path

def test_build_coin_insight(mock_root):
    # Test valid coin
    insight = _build_coin_insight("COIN_A")
    assert insight is not None
    assert insight.symbol == "COIN_A"
    assert insight.radar_status == "HOT"
    assert insight.radar_score == 85.0 # Max of scores
    assert insight.dominant_lane == "1h"
    assert "STRAT_A" in insight.approved_strategies
    assert "STRAT_B" in insight.candidate_strategies
    assert insight.radar_emoji == "🔥"
    assert insight.last_update == "12:00"

    # Test empty coin
    insight_b = _build_coin_insight("COIN_B")
    assert insight_b is not None
    assert insight_b.radar_status == "NO_DATA"
    assert insight_b.radar_score == 0.0
    assert insight_b.approved_strategies == []

    # Test missing coin
    insight_c = _build_coin_insight("COIN_MISSING")
    assert insight_c is None

def test_load_market_overview(mock_root):
    df = load_market_overview()
    
    assert not df.empty
    assert len(df) == 2 # COIN_A and COIN_B
    assert "Symbol" in df.columns
    assert "Radar" in df.columns
    assert "Score" in df.columns
    
    # Check COIN_A row
    row_a = df[df["Symbol"] == "COIN_A"].iloc[0]
    assert "🔥 HOT" in row_a["Radar"]
    assert row_a["Score"] == 85.0
    assert "STRAT_A" in row_a["Approved"]
