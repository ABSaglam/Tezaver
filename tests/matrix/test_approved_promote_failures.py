import os
import json
import pytest
from tezaver.matrix.core.approved_pool import promote_candidate_from_run

def test_promote_failures(tmp_path):
    home = str(tmp_path)
    # Setup Run Structure
    run_id = "run_fail_1"
    run_dir = tmp_path / "runs" / run_id
    os.makedirs(run_dir)
    
    # Setup Candidates
    c_dir = tmp_path / "candidates"
    os.makedirs(c_dir)
    with open(c_dir / "C1.json", "w") as f:
        json.dump({"symbol":"BTC","timeframe":"1m","build_ts":"100"}, f)
    
    # Case 1: NOT LIVE
    with open(run_dir / "meta.json", "w") as f:
        json.dump({
            "run_profile": "SNIPER",
            "candidate": {"symbol":"BTC","timeframe":"1m","build_ts":"100"}
        }, f)
    with open(run_dir / "judge.json", "w") as f:
        json.dump({"overall": "PASS"}, f)
    
    # Ensure candidates_stage dir exists but file missing
    os.makedirs(tmp_path / "candidates_stage", exist_ok=True)
    
    with pytest.raises(ValueError, match="Run must be LIVE"):
        promote_candidate_from_run(home, run_id)
        
    # Case 2: LIVE but FAIL
    with open(run_dir / "meta.json", "w") as f:
        json.dump({
            "run_profile": "LIVE",
            "candidate": {"symbol":"BTC","timeframe":"1m","build_ts":"100"}
        }, f)
    with open(run_dir / "judge.json", "w") as f:
        json.dump({"overall": "FAIL"}, f)
        
    with pytest.raises(ValueError, match="Run verdict must be PASS"):
        promote_candidate_from_run(home, run_id)
        
    # Case 3: LIVE + PASS but Stage != APPROVED
    with open(run_dir / "judge.json", "w") as f:
        json.dump({"overall": "PASS"}, f)
        
    os.makedirs(tmp_path / "candidates_stage", exist_ok=True)
    with open(tmp_path / "candidates_stage" / "C1.json", "w") as f:
        json.dump({"stage": "WAR"}, f)
        
    with pytest.raises(ValueError, match="Candidate stage is WAR, must be APPROVED"):
        promote_candidate_from_run(home, run_id)
