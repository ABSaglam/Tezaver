"""
Tests for Tezaver Sim v1.1 Preset System
"""
import pytest
from tezaver.sim import sim_presets
from tezaver.sim.sim_config import RallySimConfig

def test_get_all_presets_not_empty():
    presets = sim_presets.get_all_presets()
    assert len(presets) >= 3
    
    # Check for duplicates
    ids = [p.id for p in presets]
    assert len(ids) == len(set(ids))

def test_preset_configs_have_consistent_timeframe():
    for p in sim_presets.get_all_presets():
        assert p.timeframe == p.base_config.timeframe
        
def test_build_config_from_preset_is_copy_not_shared():
    p = sim_presets.get_preset_by_id("FAST15_SCALPER_V1")
    assert p is not None
    
    c1 = sim_presets.build_config_from_preset(p, "BTCUSDT")
    c2 = sim_presets.build_config_from_preset(p, "ETHUSDT")
    
    # Should be different objects
    assert c1 is not c2
    assert c1.symbol == "BTCUSDT"
    assert c2.symbol == "ETHUSDT"
    
    # Mutating c1 should not affect c2 or preset
    original_risk = p.base_config.risk_per_trade_pct
    c1.risk_per_trade_pct = 0.99
    
    assert c2.risk_per_trade_pct == original_risk
    assert p.base_config.risk_per_trade_pct == original_risk

def test_known_preset_values_reasonable():
    # Check H4 Trend
    p = sim_presets.get_preset_by_id("H4_TREND_V1")
    assert p.timeframe == "4h"
    assert p.base_config.tp_pct >= 0.15 # Should be large target
    # Check Context requirement
    assert p.base_config.require_trend_soul_4h_gt > 50

    # Check Scalper
    p = sim_presets.get_preset_by_id("FAST15_SCALPER_V1")
    assert p.timeframe == "15m"
    assert p.base_config.tp_pct < 0.10 # Small target
    assert p.base_config.max_horizon_bars < 20
