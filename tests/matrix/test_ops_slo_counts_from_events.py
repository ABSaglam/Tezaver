import os
import json
import time
import pytest
from tezaver.matrix.core.ops_slo import compute_slo, compute_timeline

def test_ops_slo_counts_and_timeline(tmp_path):
    home = str(tmp_path)
    
    # Create Runtime Events
    rdir = tmp_path / "cloud_runtime" / "runs" / "R1"
    os.makedirs(rdir, exist_ok=True)
    
    events = [
        {"ts": int(time.time()*1000), "type": "GLOBAL_RISK_BLOCK", "payload": "Too risky"},
        {"ts": int(time.time()*1000)-1000, "type": "STRATEGY_GAP_DETECTED"},
        {"ts": int(time.time()*1000)-2000, "type": "CLOUD_TICK_START"}
    ]
    
    with open(rdir / "events.ndjson", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
            
    # Create Alert (for creation count & timeline)
    adir = tmp_path / "alerts" / "active"
    os.makedirs(adir, exist_ok=True)
    with open(adir / "A1.json", "w") as f:
        json.dump({"created_ts": int(time.time()*1000), "level": "BLOCK", "message": "Test Alert"}, f)
        
    # Test SLO
    slo = compute_slo(home, 24)
    c = slo["counts"]
    assert c["risk_blocks"] == 1
    assert c["gap_detected"] == 1
    assert c["cloud_ticks"] == 1
    assert c["alerts_created"] == 1
    
    # Test Timeline
    tl = compute_timeline(home, 24)
    # Should have Alert, Gap, Block. Tick filtered out.
    assert len(tl) >= 3 # Alert + 2 events
    kinds = {x["kind"] for x in tl}
    assert "ALERT" in kinds
    assert "RUNTIME" in kinds
    
    # Verify Content
    alert_item = next(x for x in tl if x["kind"] == "ALERT")
    assert "Test Alert" in alert_item["detail"]
    assert "BLOCK" in alert_item["title"]
