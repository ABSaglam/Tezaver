import pytest
import json
from pathlib import Path
from tezaver.matrix.pool_court.pool_jury_v1 import build_pool_scorecard
from tezaver.matrix.pool_court.pool_judge_v1 import judge_pool
from tezaver.matrix.pool_court.pool_court_runner_v1 import run_pool_court

def create_evidence_set(reports_dir: Path, pool_enabled=True, reconcile_verdict="OK", blocked_count=0, include_live_arm=False):
    """Create fake evidence artifacts for testing."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    if pool_enabled:
        with open(reports_dir / "pool_mode_v1.json", "w") as f:
            json.dump({"pool_enabled": True, "ts": "2023-01-01T00:00:00Z"}, f)
    
    with open(reports_dir / "pool_universe_report_v1.json", "w") as f:
        json.dump({"cells_total": 5}, f)
    
    with open(reports_dir / "pool_intents_report_v1.json", "w") as f:
        json.dump({"intents_created": 3}, f)
    
    with open(reports_dir / "pool_selection_report_v1.json", "w") as f:
        json.dump({"selected_count": 2}, f)
    
    with open(reports_dir / "pool_risk_report_v1.json", "w") as f:
        json.dump({"allowed_count": 2 - blocked_count, "blocked_count": blocked_count}, f)
    
    with open(reports_dir / "pool_execution_summary_v1.json", "w") as f:
        json.dump({"planned_orders": 2, "planned_total_notional": 200.0}, f)
    
    with open(reports_dir / "restart_reconcile_report_v1.json", "w") as f:
        json.dump({"verdict": reconcile_verdict}, f)
    
    if include_live_arm:
        with open(reports_dir / "live_arm_state_report_v1.json", "w") as f:
            json.dump({"armed": True, "arm_reason": "BUNDLE_ARMED"}, f)

def test_evidence_missing_fail(tmp_path):
    """Missing evidence -> FAIL."""
    reports_dir = tmp_path / "war" / "run_001" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    # No files created -> evidence_ok = False
    
    scorecard = build_pool_scorecard(reports_dir, "war", "run_001", {})
    assert scorecard.evidence_ok is False
    
    verdict = judge_pool(scorecard)
    assert verdict.verdict == "FAIL"
    assert any(g.gate_id == "POOL_EVIDENCE_OK" and g.status == "FAIL" for g in verdict.gates)

def test_reconcile_drift_fail(tmp_path):
    """Reconcile drift -> FAIL."""
    reports_dir = tmp_path / "war" / "run_002" / "reports"
    create_evidence_set(reports_dir, pool_enabled=True, reconcile_verdict="NEEDS_SAFE_MODE")
    
    scorecard = build_pool_scorecard(reports_dir, "war", "run_002", {})
    assert scorecard.restart_reconcile_verdict == "NEEDS_SAFE_MODE"
    
    verdict = judge_pool(scorecard)
    assert verdict.verdict == "FAIL"
    assert any(g.gate_id == "RESTART_RECONCILE_OK" and g.status == "FAIL" for g in verdict.gates)
    assert "ENTER_SAFE_MODE" in verdict.suggested_actions

def test_blocked_count_improve(tmp_path):
    """Blocked intents -> IMPROVE (not FAIL)."""
    reports_dir = tmp_path / "war" / "run_003" / "reports"
    create_evidence_set(reports_dir, pool_enabled=True, reconcile_verdict="OK", blocked_count=1)
    
    scorecard = build_pool_scorecard(reports_dir, "war", "run_003", {})
    assert scorecard.blocked_count == 1
    
    verdict = judge_pool(scorecard)
    assert verdict.verdict == "IMPROVE"
    assert any(g.gate_id == "RISK_OK" and g.status == "IMPROVE" for g in verdict.gates)
    assert "TIGHTEN_POLICY_OR_FILTER" in verdict.suggested_actions

def test_all_good_pass(tmp_path):
    """All good -> PASS."""
    reports_dir = tmp_path / "war" / "run_004" / "reports"
    create_evidence_set(reports_dir, pool_enabled=True, reconcile_verdict="OK", blocked_count=0)
    
    scorecard = build_pool_scorecard(reports_dir, "war", "run_004", {})
    assert scorecard.evidence_ok is True
    assert scorecard.blocked_count == 0
    
    verdict = judge_pool(scorecard)
    assert verdict.verdict == "PASS"
    assert all(g.status in ["PASS", "WARN"] for g in verdict.gates)

def test_live_with_arm_state(tmp_path):
    """LIVE stage requires live_arm_state."""
    reports_dir = tmp_path / "live" / "run_005" / "reports"
    create_evidence_set(reports_dir, pool_enabled=True, reconcile_verdict="OK", blocked_count=0, include_live_arm=True)
    
    scorecard = build_pool_scorecard(reports_dir, "live", "run_005", {})
    assert scorecard.evidence_ok is True
    
    verdict = judge_pool(scorecard)
    assert verdict.verdict == "PASS"

def test_live_missing_arm_state_fail(tmp_path):
    """LIVE stage without live_arm_state -> evidence not OK."""
    reports_dir = tmp_path / "live" / "run_006" / "reports"
    create_evidence_set(reports_dir, pool_enabled=True, reconcile_verdict="OK", blocked_count=0, include_live_arm=False)
    
    scorecard = build_pool_scorecard(reports_dir, "live", "run_006", {})
    assert scorecard.evidence_ok is False
    assert "MISSING_REPORT:live_arm_state" in scorecard.key_notes
