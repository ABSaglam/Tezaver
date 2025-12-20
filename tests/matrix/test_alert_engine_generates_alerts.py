import os
import json
import pytest
from tezaver.matrix.core.alert_engine import scan_cloud_events_for_alerts
from tezaver.matrix.adapters.notifier_file import FileNotifier

def test_alert_engine_generates_alerts(tmp_path):
    home = str(tmp_path)
    # Setup Run
    crid = "CLOUDRUN_1"
    os.makedirs(tmp_path / "cloud_runtime" / "runs" / crid, exist_ok=True)
    
    # Write Events
    events = [
        {"ts": 1000, "type": "GLOBAL_RISK_BLOCK", "payload": {"decision": "BUY", "reason": "MAX_POS"}},
        {"ts": 2000, "type": "GLOBAL_PAUSED"},
        {"ts": 3000, "type": "STRATEGY_GAP_DETECTED", "strategy_id": "S1", "payload": {"delta": 5000}},
        {"ts": 4000, "type": "BROKER_MISCONFIG", "strategy_id": "S2", "payload": {"reason": "SECRETS_MISSING"}}
    ]
    
    with open(tmp_path / "cloud_runtime" / "runs" / crid / "events.ndjson", "w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
            
    # Scan
    notifier = FileNotifier(home)
    res = scan_cloud_events_for_alerts(home, notifier, crid)
    
    assert res["new_alerts"] == 4
    
    active = notifier.list_active()
    assert len(active) == 4
    
    types = [a["type"] for a in active]
    assert "RISK_BLOCK" in types
    assert "PAUSED" in types
    assert "GAP" in types
    assert "BROKER" in types
