import pytest
import pandas as pd
from tezaver.mac.export.story_builder import RallyStoryBuilder

def test_join_alignment_floor_vs_nearest():
    builder = RallyStoryBuilder({"sl_atr_k": 1.5})
    
    # 1. Exact Hour Match (Floor)
    event_time = pd.Timestamp("2023-12-13 07:00:00", tz="UTC")
    patterns_df = pd.DataFrame([
        {"timestamp": int(event_time.timestamp()*1000), "trigger": "macd_bull", "datetime": event_time}
    ])
    
    info = builder._get_trigger_info(event_time, patterns_df)
    assert info["trigger"] == "macd_bull"
    assert info["trigger_source"] == "join"
    assert builder.diagnostics_log[-1]["diff_min"] == 0

def test_join_alignment_nearest_30m():
    builder = RallyStoryBuilder({"sl_atr_k": 1.5})
    
    # 2. Nearest Match (25m away)
    event_time = pd.Timestamp("2023-12-13 07:25:00", tz="UTC")
    snapshot_time = pd.Timestamp("2023-12-13 07:00:00", tz="UTC")
    patterns_df = pd.DataFrame([
        {"timestamp": int(snapshot_time.timestamp()*1000), "trigger": "rsi_oversold", "datetime": snapshot_time}
    ])
    
    info = builder._get_trigger_info(event_time, patterns_df)
    assert info["trigger"] == "rsi_oversold"
    assert info["trigger_source"] == "join"
    assert builder.diagnostics_log[-1]["diff_min"] == 25.0

def test_join_alignment_unmatched_too_far():
    builder = RallyStoryBuilder({"sl_atr_k": 1.5})
    
    # 3. Too far (35m away) -> Fallback
    event_time = pd.Timestamp("2023-12-13 07:35:00", tz="UTC")
    snapshot_time = pd.Timestamp("2023-12-13 07:00:00", tz="UTC")
    patterns_df = pd.DataFrame([
        {"timestamp": int(snapshot_time.timestamp()*1000), "trigger": "rsi_oversold", "datetime": snapshot_time}
    ])
    
    info = builder._get_trigger_info(event_time, patterns_df)
    assert info["trigger"] == "unknown"
    assert info["trigger_source"] == "fallback"
    assert builder.diagnostics_log[-1]["status"] == "unmatched"

def test_resolve_rate_calculation():
    builder = RallyStoryBuilder({"sl_atr_k": 1.5})
    
    # Simulate 10 events: 6 joined, 3 fallback (macd_phase), 1 unknown fallback
    builder.total_attempts = 10
    builder.join_matched_count = 6
    builder.fallback_used_count = 4 # total fallbacks
    
    metrics = builder.get_metrics()
    assert metrics["join_coverage"] == 0.6
    assert metrics["trigger_resolve_rate"] == 1.0 # 6 join + 4 fallback / 10
