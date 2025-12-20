import os
import json
import pytest
from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick
from tezaver.matrix.core.global_risk import save_global_risk, load_global_risk

def test_cloud_kill_switch_pauses_runtime(tmp_path):
    home = str(tmp_path)
    
    # 1. Setup Paused
    cfg = load_global_risk(home)
    cfg["paused"] = True
    save_global_risk(home, cfg)
    
    # 2. Setup Active Strategy
    d = tmp_path / "cloud_registry" / "strategies" / "STRAT_A"
    os.makedirs(d, exist_ok=True)
    with open(d / "status.json", "w") as f: json.dump({"status": "ACTIVE"}, f)
    # broken strategy.json would fail tick if run, but paused should skip it
    
    # 3. Run Tick
    res = cloud_runtime_tick(home, ticks=1)
    
    # 4. Verify
    events_path = tmp_path / "cloud_runtime" / "runs" / res["cloud_run_id"] / "events.ndjson"
    lines = events_path.read_text().strip().split("\n")
    
    paused_evt = None
    tick_evt = None
    
    for l in lines:
        e = json.loads(l)
        if e["type"] == "GLOBAL_PAUSED": paused_evt = e
        if e["type"] == "CLOUD_TICK": tick_evt = e
        
    assert paused_evt
    # Tick loop continues? No, cloud_runtime_tick should create run and loop ticks.
    # Implementation: for t in range(ticks): if paused log PAUSED and continue.
    
    # Strategies processed?
    assert res["latest_strategy_results"] == {} # Should be empty
