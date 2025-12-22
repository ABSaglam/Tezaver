from tezaver.matrix.core.judge import judge_run, GateVerdict
import os
import json

def test_judge_pass(tmp_path):
    """Test that judge returns PASS with correct fixture data."""
    run_id = "run_pass"
    # MX-9301: Use contracted path structure
    run_dir = tmp_path / "out" / "matrix_runs" / "sniper" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    meta = {
        "trace": {"engine_version": "v4", "data_fingerprint": "hash"},
        "candidate": {"symbol": "BTC"}
    }
    with open(run_dir / "meta.json", "w") as f:
        json.dump(meta, f)
    
    # MX-9301: Add run-scoped reports directory
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # MX-9301: DATA_OK requires run-scoped data report
    with open(reports_dir / "data_report_v1.json", "w") as f:
        json.dump({"ok": True}, f)
    
    # MX-9301: DATA_INTEGRITY_OK requires integrity report
    with open(reports_dir / "data_integrity_v1.json", "w") as f:
        json.dump({"cand1": {"ok": True}}, f)
        
    # MX-9301: MIN_TRADES and PROFITABLE require trades
    scorecard = {
        "event_types": {"BAR": 1},
        "blocks_count": 0,
        "trades_count": 1,
        "total_pnl_raw": 100.0
    }
    
    verdict = judge_run(str(tmp_path), run_id, scorecard)
    
    assert verdict["overall"] == "PASS"
    assert all(g["status"] == "PASS" for g in verdict["gates"])

def test_judge_fail_blocks(tmp_path):
    """Test that judge returns FAIL when blocks exist or trace missing."""
    run_id = "run_fail"
    # MX-9301: Use contracted path structure
    run_dir = tmp_path / "out" / "matrix_runs" / "sniper" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
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

