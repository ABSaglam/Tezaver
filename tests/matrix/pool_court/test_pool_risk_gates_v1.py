import pytest
from tezaver.matrix.pool_court.pool_court_models_v1 import (
    PoolJuryScorecardV1,
    PoolGateResultV1
)
from tezaver.matrix.pool_court.pool_judge_v1 import judge_pool

def make_scorecard(
    blocked_count: int = 0,
    kill_switch_triggered: bool = False,
    evidence_ok: bool = True,
    restart_reconcile_verdict: str = "OK",
    selected_count: int = 5
) -> PoolJuryScorecardV1:
    return PoolJuryScorecardV1(
        run_id="test_run",
        stage="war",
        engine_version="v1",
        data_fingerprint="DF",
        config_signature="CS",
        built_ts_iso="2024-01-01",
        evidence_ok=evidence_ok,
        universe_cells=10,
        intents_created=5,
        selected_count=selected_count,
        allowed_count=selected_count - blocked_count,
        blocked_count=blocked_count,
        planned_orders=5,
        planned_total_notional=500.0,
        restart_reconcile_verdict=restart_reconcile_verdict,
        kill_switch_triggered=kill_switch_triggered,
        key_notes=[]
    )

def test_court_improve_on_risk_blocks():
    """Risk blocks cause IMPROVE verdict, not FAIL."""
    scorecard = make_scorecard(blocked_count=2)
    
    verdict = judge_pool(scorecard)
    
    # Should be IMPROVE because RISK_OK is IMPROVE
    assert verdict.verdict == "IMPROVE"
    
    risk_gate = next((g for g in verdict.gates if g.gate_id == "RISK_OK"), None)
    assert risk_gate is not None
    assert risk_gate.status == "IMPROVE"

def test_court_pass_on_no_blocks():
    """No blocks means PASS verdict."""
    scorecard = make_scorecard(blocked_count=0)
    
    verdict = judge_pool(scorecard)
    
    # Should be PASS
    assert verdict.verdict == "PASS"

def test_kill_switch_fails_court():
    """Kill switch active causes FAIL verdict."""
    scorecard = make_scorecard(kill_switch_triggered=True)
    
    verdict = judge_pool(scorecard)
    
    # Should be FAIL
    assert verdict.verdict == "FAIL"
    
    ks_gate = next((g for g in verdict.gates if g.gate_id == "KILL_SWITCH_OFF"), None)
    assert ks_gate is not None
    assert ks_gate.status == "FAIL"
