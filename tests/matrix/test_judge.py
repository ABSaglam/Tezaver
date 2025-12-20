from tezaver.matrix.core.judge import judge_run, GateVerdict
import os
import json

def test_judge_pass(tmp_path):
    run_id = "run_pass"
    run_dir = tmp_path / "runs" / run_id
    os.makedirs(run_dir)
    
    meta = {
        "trace": {"engine_version": "v4", "data_fingerprint": "hash"},
        "candidate": {"symbol": "BTC"}
    }
    with open(run_dir / "meta.json", "w") as f:
        json.dump(meta, f)
        
    scorecard = {
        "event_types": {"BAR": 1},
        "blocks_count": 0
    }
    
    # Fake data report
    drep = tmp_path / "data_reports"
    os.makedirs(drep)
    with open(drep / "latest.json", "w") as f:
        json.dump({"ok": True}, f)
        
    verdict = judge_run(str(tmp_path), run_id, scorecard)
    
    assert verdict["overall"] == "PASS"
    assert all(g["status"] == "PASS" for g in verdict["gates"])

def test_judge_fail_blocks(tmp_path):
    run_id = "run_fail"
    run_dir = tmp_path / "runs" / run_id
    os.makedirs(run_dir)
    
    # Missing trace -> FAIL
    with open(run_dir / "meta.json", "w") as f:
        json.dump({}, f)
        
    scorecard = {"blocks_count": 1} # Block -> FAIL
    
    verdict = judge_run(str(tmp_path), run_id, scorecard)
    
    assert verdict["overall"] == "FAIL"
    # Check specific gates
    statuses = {g["name"]: g["status"] for g in verdict["gates"]}
    assert statuses["NO_BLOCKS"] == "FAIL"
    assert statuses["TRACE_OK"] == "FAIL"
