import pytest
import json
from pathlib import Path
from tezaver.matrix.pool_court.pool_jury_v1 import build_pool_scorecard
from tezaver.matrix.pool_court.pool_judge_v1 import judge_pool

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)

def create_minimal_evidence(reports_dir: Path, kill_switch_triggered=False):
    """Create minimal evidence for court with optional kill switch."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    write_json(reports_dir / "pool_mode_v1.json", {"pool_enabled": True})
    write_json(reports_dir / "pool_universe_report_v1.json", {"cells_total": 5})
    write_json(reports_dir / "pool_intents_report_v1.json", {"intents_created": 3})
    write_json(reports_dir / "pool_selection_report_v1.json", {"selected_count": 2})
    
    # Risk report with kill_switch field
    risk = {
        "allowed_count": 0 if kill_switch_triggered else 2,
        "blocked_count": 2 if kill_switch_triggered else 0,
        "kill_switch": {
            "triggered": kill_switch_triggered,
            "reason": "env" if kill_switch_triggered else None
        }
    }
    write_json(reports_dir / "pool_risk_report_v1.json", risk)
    
    write_json(reports_dir / "pool_execution_summary_v1.json", {"planned_orders": 2, "planned_total_notional": 200.0})
    write_json(reports_dir / "restart_reconcile_report_v1.json", {"verdict": "OK"})

def test_kill_switch_on_court_fails(tmp_path):
    """Kill switch ON -> court verdict FAIL, gate KILL_SWITCH_OFF FAIL."""
    reports_dir = tmp_path / "war" / "run_ks_on" / "reports"
    create_minimal_evidence(reports_dir, kill_switch_triggered=True)
    
    scorecard = build_pool_scorecard(reports_dir, "war", "run_ks_on", {})
    
    assert scorecard.kill_switch_triggered is True
    
    verdict = judge_pool(scorecard)
    
    assert verdict.verdict == "FAIL"
    
    # Check KILL_SWITCH_OFF gate is FAIL
    ks_gate = next((g for g in verdict.gates if g.gate_id == "KILL_SWITCH_OFF"), None)
    assert ks_gate is not None
    assert ks_gate.status == "FAIL"
    assert "KILL_SWITCH" in ks_gate.reason
    
    # Suggested action
    assert "DISABLE_KILL_SWITCH" in verdict.suggested_actions

def test_kill_switch_off_court_passes(tmp_path):
    """Kill switch OFF -> court verdict PASS/IMPROVE (not FAIL from KS)."""
    reports_dir = tmp_path / "war" / "run_ks_off" / "reports"
    create_minimal_evidence(reports_dir, kill_switch_triggered=False)
    
    scorecard = build_pool_scorecard(reports_dir, "war", "run_ks_off", {})
    
    assert scorecard.kill_switch_triggered is False
    
    verdict = judge_pool(scorecard)
    
    # Should not be FAIL due to kill switch
    ks_gate = next((g for g in verdict.gates if g.gate_id == "KILL_SWITCH_OFF"), None)
    assert ks_gate is not None
    assert ks_gate.status == "PASS"
    
    # Verdict depends on other gates but KILL_SWITCH_OFF is PASS
    assert verdict.verdict in ["PASS", "IMPROVE"]

def test_risk_report_kill_switch_field(tmp_path):
    """Risk report kill_switch field is read by jury."""
    reports_dir = tmp_path / "war" / "run_risk_field" / "reports"
    
    # Create evidence with kill_switch in risk report
    create_minimal_evidence(reports_dir, kill_switch_triggered=True)
    
    # Verify jury reads it
    scorecard = build_pool_scorecard(reports_dir, "war", "run_risk_field", {})
    
    assert scorecard.kill_switch_triggered is True
    assert scorecard.blocked_count == 2
