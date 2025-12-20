import os
import json
import pytest
from tezaver.matrix.core.approved_pool import promote_candidate_from_run
from tezaver.matrix.core.export_package import export_candidate

def test_promote_success_and_export(tmp_path):
    home = str(tmp_path)
    
    # 1. Setup Candidate
    c_dir = tmp_path / "candidates"
    os.makedirs(c_dir)
    with open(c_dir / "C1.json", "w") as f:
        json.dump({"symbol":"BTC","timeframe":"1m","build_ts":"100","data":"stuff"}, f)
        
    # 2. Setup Run (LIVE + PASS)
    run_id = "run_live_pass"
    run_dir = tmp_path / "runs" / run_id
    os.makedirs(run_dir)
    
    with open(run_dir / "meta.json", "w") as f:
        json.dump({
            "run_profile": "LIVE",
            "candidate": {"symbol":"BTC","timeframe":"1m","build_ts":"100"},
            "trace": {"valid": True}
        }, f)
        
    with open(run_dir / "judge.json", "w") as f:
        json.dump({"overall": "PASS"}, f)
        
    with open(run_dir / "scorecard.json", "w") as f: json.dump({}, f)
    with open(run_dir / "audit.json", "w") as f: json.dump({}, f)
        
    # 3. Setup Stage (APPROVED)
    s_dir = tmp_path / "candidates_stage"
    os.makedirs(s_dir)
    with open(s_dir / "C1.json", "w") as f:
        json.dump({"stage": "APPROVED"}, f)
        
    # 4. Promote
    res = promote_candidate_from_run(home, run_id)
    assert res["candidate_id"] == "C1"
    
    # Verify Files in Approved
    app_dir = tmp_path / "approved" / "C1"
    assert (app_dir / "candidate.json").exists()
    assert (app_dir / "manifest.json").exists()
    assert (app_dir / "proofs" / "last_live_run_judge.json").exists()
    
    with open(app_dir / "manifest.json") as f:
        man = json.load(f)
        assert man["last_live_run_id"] == run_id
        assert "candidate.json" in man["checksums"]
        
    # 5. Export
    exp_res = export_candidate(home, "C1")
    exp_path = exp_res["export_path"]
    assert os.path.exists(exp_path)
    
    # Verify Export Manifest
    assert os.path.exists(exp_res["manifest_path"])
    with open(exp_res["manifest_path"]) as f:
        eman = json.load(f)
        assert eman["version"] == "export_v1"
        assert eman["candidate_id"] == "C1"
        assert "candidate.json" in eman["files"]
        assert "candidate.json" in eman["sha256"]
        assert eman["sha256"]["candidate.json"] != ""
