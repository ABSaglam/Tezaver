import pytest
import pandas as pd
import json
from pathlib import Path
from tezaver.mac.export.fingerprint import calculate_config_signature, calculate_data_fingerprint
from tezaver.mac.export.story_builder import RallyStoryBuilder

def test_config_signature_determinism():
    config1 = {"sl_atr_k": 1.5, "version": "v1"}
    config2 = {"version": "v1", "sl_atr_k": 1.5}
    sig1 = calculate_config_signature(config1)
    sig2 = calculate_config_signature(config2)
    assert sig1 == sig2
    assert len(sig1) == 64

def test_story_id_format_utc():
    builder = RallyStoryBuilder({"sl_atr_k": 1.5})
    event_time = pd.Timestamp("2023-12-13 07:00:00")
    event_row = pd.Series({"event_time": event_time, "event_tf": "15m"})
    
    # Mock data
    history_df = pd.DataFrame([{"timestamp": int(event_time.timestamp()*1000), "close": 41000.0}])
    patterns_df = pd.DataFrame(columns=["trigger", "timestamp"])
    
    story = builder.build_story("BTCUSDT", event_row, history_df, patterns_df, [], {}, {}, [], [])
    # 20231213_0700 format remains but stored internally as UTC
    assert story["story_id"] == "BTCUSDT_15m_20231213_0700"
    assert "event_time_utc" in story["entry"]
    assert "Z" in story["entry"]["event_time_utc"] or "+00:00" in story["entry"]["event_time_utc"]

def test_join_coverage_metrics():
    builder = RallyStoryBuilder({"sl_atr_k": 1.5})
    builder.total_build_attempts = 10
    builder.successful_joins = 8
    metrics = builder.get_join_metrics()
    assert metrics["join_coverage"] == 0.8
    assert metrics["join_unmatched_count"] == 2
