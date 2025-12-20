import os
import json
import pytest
from tezaver.matrix.core.live_recovery import recover_live_runs

def test_live_recovery_warnings(tmp_path):
    home = str(tmp_path)
    runs = tmp_path / "runs"
    os.makedirs(runs)
    
    # R1: Healthy
    r1 = runs / "R1"
    os.makedirs(r1)
    with open(r1 / "live_state.json", "w") as f: f.write("{}")
    with open(r1 / "meta.json", "w") as f: f.write("{}")
    with open(r1 / "events.ndjson", "w") as f: f.write("")
    
    # R2: Broken
    r2 = runs / "R2"
    os.makedirs(r2)
    with open(r2 / "live_state.json", "w") as f: f.write("{}")
    
    rep = recover_live_runs(home)
    assert rep["runs_scanned"] == 2
    assert len(rep["warnings"]) == 2 # R2 miss meta, R2 miss events
    assert "R2" in rep["warnings"][0]
