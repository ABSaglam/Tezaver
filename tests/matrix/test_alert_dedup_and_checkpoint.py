import os
import json
import pytest
from tezaver.matrix.core.alert_engine import scan_cloud_events_for_alerts
from tezaver.matrix.adapters.notifier_file import FileNotifier

def test_alert_dedup_and_checkpoint(tmp_path):
    home = str(tmp_path)
    crid = "CLOUDRUN_1"
    os.makedirs(tmp_path / "cloud_runtime" / "runs" / crid, exist_ok=True)
    
    events = [{"ts": 1000, "type": "GLOBAL_PAUSED"}]
    p_events = tmp_path / "cloud_runtime" / "runs" / crid / "events.ndjson"
    
    with open(p_events, "w") as f:
        f.write(json.dumps(events[0]) + "\n")
        
    notifier = FileNotifier(home)
    
    # 1. First Scan
    res1 = scan_cloud_events_for_alerts(home, notifier, crid)
    assert res1["new_alerts"] == 1
    assert res1["scanned"] == 1
    
    # 2. Second Scan (No new events)
    res2 = scan_cloud_events_for_alerts(home, notifier, crid)
    assert res2["new_alerts"] == 0
    assert res2["scanned"] == 0 # Checkpoint worked
    
    # 3. Append Duplicate Logic Event (Dedup)
    # We append exact same event type. Engine generates SAME ID.
    # Checkpoint will advance, but FileNotifier won't duplicate file (overwrite same ID).
    # wait... FileNotifier writes to ID.json. If ID is same, file is same.
    # So "new_alerts" returned by engine counts emitted calls.
    # But effectively it is deduped in storage.
    
    with open(p_events, "a") as f:
        f.write(json.dumps(events[0]) + "\n") # Same event again
        
    res3 = scan_cloud_events_for_alerts(home, notifier, crid)
    assert res3["scanned"] == 1
    # Engine logic re-emits if checkpoint passed, but persistence dedups by ID.
    # Our test engine returns number of emit calls.
    assert res3["new_alerts"] == 1 
    
    active = notifier.list_active()
    assert len(active) == 1 # Still 1 file because ID is deterministic
