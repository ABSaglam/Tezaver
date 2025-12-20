import os
import json
from tezaver.matrix.core.incident import build_incident_bundle

def test_incident_bundle_creation(tmp_path):
    home = tmp_path / "home"
    run_id = "run_test"
    run_dir = home / "runs" / run_id
    os.makedirs(run_dir)
    
    # Create fake run files
    (run_dir / "meta.json").write_text("{}")
    (run_dir / "events.ndjson").write_text("{}\n" * 10)
    
    iid = build_incident_bundle(str(home), run_id, "Test Reason")
    
    inc_dir = home / "incidents" / iid
    assert inc_dir.exists()
    assert (inc_dir / "meta.json").exists()
    assert (inc_dir / "events_tail.ndjson").exists()
    assert (inc_dir / "manifest.json").exists()
    
    with open(inc_dir / "manifest.json") as f:
        m = json.load(f)
        assert m["reason"] == "Test Reason"
