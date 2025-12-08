"""
Tests for Tezaver Sim v1.5 - Strategy Promotion
"""

import pytest
from tezaver.sim.sim_promotion import (
    StrategyPromotionConfig,
    compute_promotion_for_preset,
    compute_promotion_for_symbol,
    StrategyPromotionSummary
)

@pytest.fixture
def promo_config():
    return StrategyPromotionConfig(
        min_trades_strong=40,
        min_trades_weak=15,
        min_score_candidate=55.0,
        min_score_approved=70.0,
        min_win_rate_approved=0.52,
        max_dd_approved=-0.30,
        max_dd_candidate=-0.35,
        min_expectancy_approved=0.0
    )

def test_promotion_approved(promo_config):
    """Test APPROVED criteria."""
    decision = compute_promotion_for_preset(
        preset_id="TEST_APPROVED",
        affinity_score=80.0,
        grade="A",
        trade_count=50,       # > 40
        win_rate=0.60,        # > 0.52
        net_pnl_pct=0.20,
        max_drawdown_pct=-0.20, # > -0.30
        expectancy_pct=1.5,   # > 0
        config=promo_config
    )
    
    assert decision.status == "APPROVED"
    assert decision.reliability == "reliable"

def test_promotion_candidate(promo_config):
    """Test CANDIDATE criteria."""
    # Case 1: Low score but enough trades/DD
    decision = compute_promotion_for_preset(
        preset_id="TEST_CANDIDATE",
        affinity_score=60.0,  # > 55 but < 70
        grade="B",
        trade_count=20,       # > 15 but < 40
        win_rate=0.45,        # Low WR shouldn't disqualify candidate if score is ok (Wait, score logic)
                              # Logic says: Candidate if not approved AND score >= 55 AND trades >= 15 AND DD >= -35
        net_pnl_pct=0.05,
        max_drawdown_pct=-0.32, # > -0.35 but < -0.30 (maybe)
        expectancy_pct=0.5,
        config=promo_config
    )
    
    assert decision.status == "CANDIDATE"
    assert decision.reliability == "low_data" # 20 < 40

def test_promotion_rejected(promo_config):
    """Test REJECTED criteria."""
    # Case 1: Too few trades
    d1 = compute_promotion_for_preset(
        preset_id="REJECT_TRADES",
        affinity_score=90.0,
        grade="A",
        trade_count=10, # < 15
        win_rate=0.80,
        net_pnl_pct=0.50,
        max_drawdown_pct=-0.10,
        expectancy_pct=2.0,
        config=promo_config
    )
    assert d1.status == "REJECTED"
    
    # Case 2: Drawdown too deep
    d2 = compute_promotion_for_preset(
        preset_id="REJECT_DD",
        affinity_score=80.0,
        grade="A",
        trade_count=50,
        win_rate=0.60,
        net_pnl_pct=0.10,
        max_drawdown_pct=-0.40, # < -0.35
        expectancy_pct=1.0,
        config=promo_config
    )
    assert d2.status == "REJECTED"
    
    # Case 3: Low Score
    d3 = compute_promotion_for_preset(
        preset_id="REJECT_SCORE",
        affinity_score=40.0, # < 55
        grade="C",
        trade_count=50,
        win_rate=0.40,
        net_pnl_pct=-0.10,
        max_drawdown_pct=-0.20,
        expectancy_pct=-0.5,
        config=promo_config
    )
    assert d3.status == "REJECTED"

def test_compute_promotion_for_symbol():
    """Test symbol level aggregation."""
    # Mock affinity data (dict format)
    affinity_data = {
        "presets": {
            "STRAT_A": {
                "affinity_score": 85.0,
                "affinity_grade": "A",
                "num_trades": 60,
                "win_rate": 0.65,
                "net_pnl_pct": 0.30,
                "max_drawdown_pct": -0.15,
                "expectancy_pct": 1.2
            },
            "STRAT_B": {
                "affinity_score": 30.0,
                "affinity_grade": "D",
                "num_trades": 5,
                "win_rate": 0.20,
                "net_pnl_pct": -0.50,
                "max_drawdown_pct": -0.60,
                "expectancy_pct": -2.0
            }
        }
    }
    
    summary = compute_promotion_for_symbol(
        symbol="BTCUSDT",
        affinity_data=affinity_data,
        scoreboard_data={}
    )
    
    assert summary.symbol == "BTCUSDT"
    assert len(summary.strategies) == 2
    assert summary.strategies["STRAT_A"].status == "APPROVED"
    assert summary.strategies["STRAT_B"].status == "REJECTED"
