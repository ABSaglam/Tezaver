import os
import json
import pytest
from tezaver.matrix.core.rehearsal import run_rehearsal

def test_rehearsal_relaxed_checks_in_paper(tmp_path):
    home = str(tmp_path)
    
    # PAPER mode
    os.makedirs(tmp_path / "cloud_runtime", exist_ok=True)
    with open(tmp_path / "cloud_runtime" / "broker_config.json", "w") as f:
        json.dump({"mode": "PAPER"}, f)
        
    # NO secrets (should be relaxed)
    # NO userstream connected (should be relaxed)
    
    report = run_rehearsal(home, None)
    
    # RH-06 and RH-07 should PASS in PAPER mode
    rh06 = next(c for c in report["checks"] if c["code"] == "RH-06")
    rh07 = next(c for c in report["checks"] if c["code"] == "RH-07")
    
    assert rh06["status"] == "PASS"
    assert rh07["status"] == "PASS"
    assert "Not required for PAPER" in rh06["detail"]
    assert "Not required for PAPER" in rh07["detail"]
