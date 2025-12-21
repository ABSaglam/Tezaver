import pytest
import os
import json
from pathlib import Path
from tezaver.matrix.core.judge import judge_run

def test_judge_data_ok_pass(tmp_path):
    # Setup mock run structure
    home = str(tmp_path)
    run_id = "war_test_123"
    run_dir = tmp_path / "out" / "matrix_runs" / "war" / run_id
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True)
    
    # Create valid data report
    report = {"ok": True, "resolved_rate": 1.0}
    with open(reports_dir / "data_report_v1.json", "w") as f:
        json.dump(report, f)
    
    # Mock meta.json
    with open(run_dir / "meta.json", "w") as f:
        json.dump({"trace": {"engine_version": "v4", "data_fingerprint": "fp1"}}, f)
        
    scorecard = {"event_types": ["test"], "trades_count": 1, "total_pnl_raw": 10.0}
    
    # We need to ensure judge_run uses the tmp_path as home
    # The judge_run internally uses get_data_report_path which defaults to out/matrix_runs/...
    # But it accepts home arg.
    
    result = judge_run(home, run_id, scorecard)
    
    data_gate = next(g for g in result["gates"] if g["name"] == "DATA_OK")
    assert data_gate["status"] == "PASS"

def test_judge_data_ok_fail_missing(tmp_path):
    home = str(tmp_path)
    run_id = "live_test_456"
    run_dir = tmp_path / "out" / "matrix_runs" / "live" / run_id
    run_dir.mkdir(parents=True)
    
    with open(run_dir / "meta.json", "w") as f:
        json.dump({"trace": {"engine_version": "v4", "data_fingerprint": "fp1"}}, f)
        
    scorecard = {"event_types": ["test"], "trades_count": 0}
    
    result = judge_run(home, run_id, scorecard)
    
    data_gate = next(g for g in result["gates"] if g["name"] == "DATA_OK")
    assert data_gate["status"] == "FAIL"
    assert "MISSING_RUN_SCOPED_REPORT" in data_gate["reason"]

def test_judge_data_ok_fail_quality(tmp_path):
    home = str(tmp_path)
    run_id = "sniper_test_789"
    run_dir = tmp_path / "out" / "matrix_runs" / "sniper" / run_id
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True)
    
    # Create invalid data report
    report = {"ok": False, "issues": ["Gap found"]}
    with open(reports_dir / "data_report_v1.json", "w") as f:
        json.dump(report, f)
        
    with open(run_dir / "meta.json", "w") as f:
        json.dump({"trace": {"engine_version": "v4", "data_fingerprint": "fp1"}}, f)
        
    scorecard = {"event_types": ["test"]}
    
    result = judge_run(home, run_id, scorecard)
    
    data_gate = next(g for g in result["gates"] if g["name"] == "DATA_OK")
    assert data_gate["status"] == "FAIL"
    assert data_gate["reason"] == "DATA_QUALITY_FAIL"
