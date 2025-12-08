"""
Tests for Strategy Affinity UI Logic (Explanation Cards)
"""
import pytest
from unittest.mock import MagicMock
from tezaver.ui.explanation_cards import (
    build_strategy_affinity_summary_tr,
    CoinExplanationContext
)

def test_build_strategy_affinity_summary_none():
    # 1. No affinity data
    ctx = CoinExplanationContext(symbol="TEST")
    res = build_strategy_affinity_summary_tr(ctx)
    assert res is None

    # 2. Empty affinity data
    ctx.sim_affinity = {}
    assert build_strategy_affinity_summary_tr(ctx) is None
    
    # 3. Empty presets
    ctx.sim_affinity = {"presets": {}}
    assert build_strategy_affinity_summary_tr(ctx) is None

def test_build_strategy_affinity_summary_reliable():
    # Mock data
    presets = {
        "P1": {
            "preset_id": "P1",
            "affinity_score": 85.0,
            "affinity_grade": "A",
            "status": "reliable",
            "win_rate": 0.65,
            "net_pnl_pct": 0.40,
            "max_drawdown_pct": -0.15,
            "num_trades": 50
        },
        "P2": {
            "preset_id": "P2",
            "affinity_score": 60.0,
            "status": "reliable"
        }
    }
    ctx = CoinExplanationContext(symbol="BTC", sim_affinity={"presets": presets})
    
    res = build_strategy_affinity_summary_tr(ctx)
    
    assert res is not None
    assert "P1" in res
    assert "85" in res
    assert "%65.0" in res
    assert "güvenilir" not in res # Wait, "reliable" status logic adds "istatistiksel açıdan anlamlı"
    assert "istatistiksel açıdan anlamlı" in res

def test_build_strategy_affinity_summary_low_data():
    # Only low data
    presets = {
        "P1": {
            "preset_id": "P1",
            "affinity_score": 90.0,
            "affinity_grade": "A+",
            "status": "low_data",
            "win_rate": 1.0,
            "net_pnl_pct": 0.10,
            "max_drawdown_pct": 0.0,
            "num_trades": 3
        }
    }
    ctx = CoinExplanationContext(symbol="ETH", sim_affinity={"presets": presets})
    
    res = build_strategy_affinity_summary_tr(ctx)
    
    assert res is not None
    assert "P1" in res
    assert "90" in res
    assert "örnek sayısı düşük" in res
    assert "kesinlik taşımaz" in res

def test_build_strategy_affinity_priority():
    # Use case: Low data has higher score than Reliable
    # Should pick Reliable
    presets = {
        "RELIABLE_OK": {
            "preset_id": "RELIABLE_OK",
            "affinity_score": 60.0,
            "status": "reliable", # "Low score"
            "win_rate": 0.5,
            "net_pnl_pct": 0.1,
            "max_drawdown_pct": -0.2,
            "num_trades": 30
        },
        "LOW_DATA_GREAT": {
            "preset_id": "LOW_DATA_GREAT",
            "affinity_score": 95.0, # Higher score
            "status": "low_data",
            "num_trades": 2
        }
    }
    ctx = CoinExplanationContext(symbol="SOL", sim_affinity={"presets": presets})
    
    res = build_strategy_affinity_summary_tr(ctx)
    
    # Should contain RELIABLE_OK because we prioritize reliability
    assert "RELIABLE_OK" in res
    assert "LOW_DATA_GREAT" not in res
