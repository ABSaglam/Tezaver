import os
import json
import pytest
from tezaver.matrix.core.rehearsal import run_rehearsal

def test_rehearsal_no_go_fail_codes(tmp_path):
    home = str(tmp_path)
    
    # Setup failing conditions
    os.makedirs(tmp_path / "cloud_runtime", exist_ok=True)
    os.makedirs(tmp_path / "alerts" / "active", exist_ok=True)
    
    # RH-05: Global Pause ON
    with open(tmp_path / "cloud_runtime" / "global_risk.json", "w") as f:
        json.dump({"paused": True}, f)
        
    # RH-04: CRIT Alert
    with open(tmp_path / "alerts" / "active" / "A1.json", "w") as f:
        json.dump({"level": "CRITICAL"}, f)
        
    report = run_rehearsal(home, None)
    
    assert report["go"] is False
    assert report["overall"] == "NO_GO"
    assert "RH-04" in report["fail_codes"]
    assert "RH-05" in report["fail_codes"]
