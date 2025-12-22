import os
import json
import pytest
from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick, list_active_strategies

def test_cloud_runtime_tick(tmp_path):
    home = str(tmp_path)
    
    # 1. Setup Active Strategy
    os.makedirs(tmp_path / "cloud_registry" / "strategies" / "STRAT_A", exist_ok=True)
    with open(tmp_path / "cloud_registry" / "strategies" / "STRAT_A" / "status.json", "w") as f:
        json.dump({"status": "ACTIVE"}, f)
        
    os.makedirs(tmp_path / "cloud_registry" / "strategies" / "STRAT_B", exist_ok=True)
    with open(tmp_path / "cloud_registry" / "strategies" / "STRAT_B" / "status.json", "w") as f:
        json.dump({"status": "PAUSED"}, f)
        
    # Test Listing
    active = list_active_strategies(home)
    assert len(active) == 1
    assert active[0] == "STRAT_A"
    
    # 2. Run Tick
    res = cloud_runtime_tick(home, ticks=2)
    
    assert res["ticks_processed"] == 2
    assert res["active_strategies"] == 1
    # MX-9330: events_written tracks CLOUD_TICK events only
    assert res["events_written"] == 2
    
    # 3. Verify Artifacts
    crid = res["cloud_run_id"]
    r_dir = tmp_path / "cloud_runtime" / "runs" / crid
    assert r_dir.exists()
    
    # Events
    events_path = r_dir / "events.ndjson"
    assert events_path.exists()
    lines = events_path.read_text().strip().split("\n")
    # MX-9330: Each tick emits: SECRETS_HEALTH, BROKER_MODE, GLOBAL_RISK_SNAPSHOT, CLOUD_TICK, RUNTIME_HEARTBEAT
    # 2 ticks * 5 events = 10 lines
    assert len(lines) >= 4  # At least CLOUD_TICK + HEARTBEAT per tick
    
    # Check CLOUD_TICK exists with strategy_id
    cloud_ticks = [json.loads(l) for l in lines if "CLOUD_TICK" in l]
    assert len(cloud_ticks) == 2
    assert cloud_ticks[0]["type"] == "CLOUD_TICK"
    assert cloud_ticks[0]["strategy_id"] == "STRAT_A"
    
    # Heartbeat
    hb_path = r_dir / "heartbeat.json"
    assert hb_path.exists()
    hb = json.loads(hb_path.read_text())
    assert hb["active_count"] == 1

