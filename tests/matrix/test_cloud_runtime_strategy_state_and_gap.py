import os
import json
import pytest
from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick, load_strategy_state

def test_cloud_runtime_strategy_state_and_gap(tmp_path):
    home = str(tmp_path)
    
    # 1. Setup Bars
    bars = [
        {"ts": 1000, "close": 100, "closed": True}, # Bar 0
        {"ts": 2000, "close": 101, "closed": True}, # Bar 1 (TF=1000)
        {"ts": 5000, "close": 102, "closed": True}  # Bar 2 (Gap! 5000 > 2000 + 1.1*1000)
    ]
    bars_path = tmp_path / "bars.json"
    with open(bars_path, "w") as f:
        json.dump(bars, f)
        
    # 2. Setup Strategies
    # STRAT_A: Valid with bars
    s_a = tmp_path / "cloud_registry" / "strategies" / "STRAT_A"
    os.makedirs(s_a, exist_ok=True)
    with open(s_a / "status.json", "w") as f: json.dump({"status": "ACTIVE"}, f)
    with open(s_a / "strategy.json", "w") as f:
        json.dump({
            "timeframe": "1s", # 1000ms
            "bars_source": {"type": "JSON_FILE", "path": str(bars_path)}
        }, f)
        
    # STRAT_B: No Bars
    s_b = tmp_path / "cloud_registry" / "strategies" / "STRAT_B"
    os.makedirs(s_b, exist_ok=True)
    with open(s_b / "status.json", "w") as f: json.dump({"status": "ACTIVE"}, f)
    with open(s_b / "strategy.json", "w") as f: json.dump({"timeframe": "15m"}, f)
    
    # 3. Run Tick
    res = cloud_runtime_tick(home, ticks=1, steps_per_strategy=5)
    
    # 4. Verify STRAT_A
    state_a = load_strategy_state(home, "STRAT_A")
    assert state_a["cursor"] == 3 # All 3 bars processed
    assert state_a["last_ts"] == 5000
    
    # Verify Events
    events_path = tmp_path / "cloud_runtime" / "runs" / res["cloud_run_id"] / "events.ndjson"
    lines = events_path.read_text().strip().split("\n")
    
    gap_detected = False
    reconnect = False
    skipped_b = False
    
    for l in lines:
        e = json.loads(l)
        if e["type"] == "STRAT_GAP_DETECTED" or e["type"] == "STRATEGY_GAP_DETECTED": # Check exact type name used in implementation
             gap_detected = True
        if e["type"] == "STRATEGY_RECONNECT":
             reconnect = True
        if e["type"] == "STRATEGY_SKIPPED" and e["strategy_id"] == "STRAT_B":
             skipped_b = True
             
    assert gap_detected
    assert reconnect
    assert skipped_b
