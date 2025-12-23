import pytest
from tezaver.matrix.pool_court.pool_judge_v1 import judge_pool
from tezaver.matrix.pool_court.pool_court_models_v1 import PoolJuryScorecardV1

def make_scorecard(blocked_reasons: dict):
    # Calculate counts from reasons
    blocked_count = sum(blocked_reasons.values())
    
    return PoolJuryScorecardV1(
        run_id="test", stage="war", engine_version="v1", data_fingerprint="df", config_signature="cs",
        built_ts_iso="2024", evidence_ok=True, universe_cells=10, intents_created=5,
        selected_count=5, allowed_count=5-blocked_count, blocked_count=blocked_count,
        planned_orders=5-blocked_count, planned_total_notional=100.0,
        restart_reconcile_verdict="OK", kill_switch_triggered=False,
        blocked_reasons_count=blocked_reasons,
        limits={}, key_notes=[]
    )

def test_judge_global_risk_improve():
    """Global cap block triggers GLOBAL_RISK_OK: IMPROVE."""
    sc = make_scorecard({"GLOBAL_NOTIONAL_CAP": 2})
    
    verdict = judge_pool(sc)
    
    assert verdict.verdict == "IMPROVE"
    gate = next(g for g in verdict.gates if g.gate_id == "GLOBAL_RISK_OK")
    assert gate.status == "IMPROVE"
    assert "Global cap blocks: 2" in gate.reason

def test_judge_per_coin_risk_improve():
    """Per-coin block triggers PER_COIN_RISK_OK: IMPROVE."""
    sc = make_scorecard({"PER_COIN_CAP": 1})
    
    verdict = judge_pool(sc)
    
    assert verdict.verdict == "IMPROVE"
    gate = next(g for g in verdict.gates if g.gate_id == "PER_COIN_RISK_OK")
    assert gate.status == "IMPROVE"
    assert "Per-coin blocks" in gate.reason

def test_judge_all_pass():
    """No blocks triggers PASS."""
    sc = make_scorecard({})
    
    verdict = judge_pool(sc)
    
    assert verdict.verdict == "PASS"
    gate_g = next(g for g in verdict.gates if g.gate_id == "GLOBAL_RISK_OK")
    assert gate_g.status == "PASS"
    gate_c = next(g for g in verdict.gates if g.gate_id == "PER_COIN_RISK_OK")
    assert gate_c.status == "PASS"

def test_generic_risk_handling():
    """Other reasons trigger generic RISK_OK: IMPROVE."""
    sc = make_scorecard({"MISSING_POLICY": 3})
    
    verdict = judge_pool(sc)
    
    assert verdict.verdict == "IMPROVE"
    gate = next(g for g in verdict.gates if g.gate_id == "RISK_OK")
    assert gate.status == "IMPROVE"
    assert "Other blocks: 3" in gate.reason
