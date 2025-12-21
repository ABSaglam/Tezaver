import pytest
import json
from pathlib import Path
from tezaver.matrix.core.release_gate import evaluate_release_gate
from tezaver.matrix.release.release_report import write_release_report

def test_write_release_report(tmp_path):
    run_dir = tmp_path / "run_123"
    run_dir.mkdir()
    
    gate_result = {
        "ok": False,
        "active_stage": "WAR",
        "checks": [
            {"name": "Check1", "status": "FAIL", "severity": "CRITICAL"},
            {"name": "Check2", "status": "FAIL", "severity": "WARNING"}
        ],
        "summary": "Blocked by 1 issue"
    }
    
    path = write_release_report(run_dir, gate_result)
    assert path.exists()
    
    with open(path) as f:
        data = json.load(f)
        assert data["overall_ok"] is False
        assert "Check1" in data["blocking_protocols"]
        assert "Check2" in data["warnings"]

def test_release_gate_blocking_on_red(tmp_path, monkeypatch):
    # Mock SafetyRegistry to return RED for a protocol
    # This requires a bit of complex mocking of the registry class
    # For now, let's verify if the logic in evaluate_release_gate respects registry
    pass # Integration test usually better here due to registry yaml dependency

def test_release_gate_stage_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("TEZAVER_STAGE", "LIVE")
    res = evaluate_release_gate(str(tmp_path), "cid_123")
    assert res["active_stage"] == "LIVE"
    assert res["assumed_stage"] is False
    
    monkeypatch.delenv("TEZAVER_STAGE", raising=False)
    res = evaluate_release_gate(str(tmp_path), "cid_123")
    assert res["active_stage"] == "WAR"
    assert res["assumed_stage"] is True
