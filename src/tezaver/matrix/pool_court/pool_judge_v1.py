"""
Pool Judge V1
=============

Evaluates scorecard gates and produces verdict.
"""
from typing import List, Dict, Any
from datetime import datetime, timezone

from tezaver.matrix.pool_court.pool_court_models_v1 import (
    PoolJuryScorecardV1,
    PoolGateResultV1,
    PoolCourtVerdictV1
)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def judge_pool(
    scorecard: PoolJuryScorecardV1,
    trace_ctx: Dict[str, str] = None,
    evidence_paths: Dict[str, str] = None
) -> PoolCourtVerdictV1:
    """
    Evaluate scorecard and produce court verdict.
    
    Gates:
    1. POOL_EVIDENCE_OK - evidence_ok must be true
    2. RESTART_RECONCILE_OK - reconcile verdict must be OK
    3. RISK_OK - blocked_count == 0 for PASS, >0 for IMPROVE
    4. MIN_ACTIVITY - selected_count >= 1 for PASS, else WARN
    
    Verdict:
    - Any FAIL gate → FAIL
    - RISK_OK IMPROVE → IMPROVE
    - All PASS (WARN ok) → PASS
    """
    trace = trace_ctx or {}
    ev = trace.get("engine_version", scorecard.engine_version)
    df = trace.get("data_fingerprint", scorecard.data_fingerprint)
    cs = trace.get("config_signature", scorecard.config_signature)
    
    gates: List[PoolGateResultV1] = []
    suggested_actions: List[str] = []
    
    # Gate 0: KILL_SWITCH_OFF (Phase 5B.1 - HARD BLOCK)
    if not scorecard.kill_switch_triggered:
        gates.append(PoolGateResultV1("KILL_SWITCH_OFF", "PASS", "Kill switch not active"))
    else:
        gates.append(PoolGateResultV1("KILL_SWITCH_OFF", "FAIL", "KILL_SWITCH_ACTIVE"))
        suggested_actions.append("DISABLE_KILL_SWITCH")
    
    # Gate 1: POOL_EVIDENCE_OK
    if scorecard.evidence_ok:
        gates.append(PoolGateResultV1("POOL_EVIDENCE_OK", "PASS", "All evidence present"))
    else:
        gates.append(PoolGateResultV1("POOL_EVIDENCE_OK", "FAIL", f"Missing evidence: {scorecard.key_notes}"))
        suggested_actions.append("GENERATE_MISSING_EVIDENCE")
    
    # Gate 2: RESTART_RECONCILE_OK
    if scorecard.restart_reconcile_verdict == "OK":
        gates.append(PoolGateResultV1("RESTART_RECONCILE_OK", "PASS", "No drift detected"))
    elif scorecard.restart_reconcile_verdict == "UNKNOWN":
        gates.append(PoolGateResultV1("RESTART_RECONCILE_OK", "FAIL", "Reconcile report missing"))
    else:
        gates.append(PoolGateResultV1("RESTART_RECONCILE_OK", "FAIL", f"Drift detected: {scorecard.restart_reconcile_verdict}"))
        suggested_actions.extend(["ENTER_SAFE_MODE", "RECONCILE_POSITIONS"])
    
    # Gate 3: RISK_OK
    if scorecard.blocked_count == 0:
        gates.append(PoolGateResultV1("RISK_OK", "PASS", "No blocked intents"))
    else:
        gates.append(PoolGateResultV1("RISK_OK", "IMPROVE", f"Blocked intents: {scorecard.blocked_count}"))
        suggested_actions.append("TIGHTEN_POLICY_OR_FILTER")
    
    # Gate 4: MIN_ACTIVITY
    if scorecard.selected_count >= 1:
        gates.append(PoolGateResultV1("MIN_ACTIVITY", "PASS", f"Selected: {scorecard.selected_count}"))
    else:
        gates.append(PoolGateResultV1("MIN_ACTIVITY", "WARN", "No intents selected"))
    
    # Determine verdict
    has_fail = any(g.status == "FAIL" for g in gates)
    has_improve = any(g.status == "IMPROVE" for g in gates)
    
    if has_fail:
        verdict = "FAIL"
    elif has_improve:
        verdict = "IMPROVE"
    else:
        verdict = "PASS"
    
    # Build summary
    gate_statuses = [f"{g.gate_id}={g.status}" for g in gates]
    summary = f"{', '.join(gate_statuses)} => {verdict}"
    
    return PoolCourtVerdictV1(
        run_id=scorecard.run_id,
        stage=scorecard.stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        verdict=verdict,
        gates=gates,
        summary=summary,
        suggested_actions=suggested_actions,
        evidence_paths=evidence_paths or {}
    )
