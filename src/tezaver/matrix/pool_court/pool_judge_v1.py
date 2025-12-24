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
    
    # Gate 3: RISK_OK (Granular - Phase 6A.3)
    # 3a. GLOBAL_RISK_OK
    reason_counts = scorecard.blocked_reasons_count
    if reason_counts.get("GLOBAL_NOTIONAL_CAP", 0) > 0:
        gates.append(PoolGateResultV1("GLOBAL_RISK_OK", "IMPROVE", f"Global cap blocks: {reason_counts['GLOBAL_NOTIONAL_CAP']}"))
        suggested_actions.append("INCREASE_GLOBAL_CAP")
    else:
        gates.append(PoolGateResultV1("GLOBAL_RISK_OK", "PASS", "Global cap OK"))
        
    # 3b. PER_COIN_RISK_OK
    per_coin_blocks = reason_counts.get("PER_COIN_CAP", 0)
    if per_coin_blocks > 0:
        gates.append(PoolGateResultV1("PER_COIN_RISK_OK", "IMPROVE", f"Per-coin blocks: {per_coin_blocks}"))
    else:
        gates.append(PoolGateResultV1("PER_COIN_RISK_OK", "PASS", "Per-coin caps OK"))

    # 3c. RISK_OK (Generic catch-all for other reasons)
    # Valid reasons: RISK_LIMIT (generic), MISSING_POLICY, etc.
    # We filter out KILL_SWITCH (handled by Gate 0) and already handled above
    other_blocks = scorecard.blocked_count - (reason_counts.get("KILL_SWITCH", 0) + 
                                              reason_counts.get("GLOBAL_NOTIONAL_CAP", 0) + 
                                              reason_counts.get("PER_COIN_CAP", 0))
    if other_blocks > 0:
        gates.append(PoolGateResultV1("RISK_OK", "IMPROVE", f"Other blocks: {other_blocks}"))
    else:
        gates.append(PoolGateResultV1("RISK_OK", "PASS", "No other blocks"))
    
    # Gate 4: MIN_ACTIVITY
    # Check for specific skip reasons
    skipped_reasons = []
    
    # 4a. Cert Missing
    if scorecard.skipped_reasons_count.get("SKIPPED_NOT_CERTIFIED", 0) > 0:
        gates.append(PoolGateResultV1("SNIPER_CERT_OK", "FAIL", "Missing or not passed (SKIPPED_NOT_CERTIFIED > 0)"))
        skipped_reasons.append("SKIPPED_NOT_CERTIFIED")
        suggested_actions.append("CHECK_SNIPER_CERT")
    else:
        # If we have intents created, then cert is implicitly OK or not required for Candidate stage (though War requires it)
        # But if total intents created > 0, we assume Cert OK for at least some.
        pass
        
    # 4b. No Activity
    # If not certified, we already handle it. If certified but no intents (e.g. no trigger), that's also SKIP (idle)
    if scorecard.intents_created == 0:
         gates.append(PoolGateResultV1("MIN_ACTIVITY", "WARN", "No intents created"))
         if "SKIPPED_NOT_CERTIFIED" not in skipped_reasons:
             skipped_reasons.append("NO_INTENTS")
    elif scorecard.selected_count == 0:
         # Intents created but none selected (maybe QC fail or Strategy constraints)
         gates.append(PoolGateResultV1("MIN_ACTIVITY", "WARN", "No intents selected"))
         skipped_reasons.append("NO_SELECTION")
    else:
         gates.append(PoolGateResultV1("MIN_ACTIVITY", "PASS", f"Selected: {scorecard.selected_count}"))
    
    # Determine verdict and decision_action
    
    blocked_reasons = [k for k, v in scorecard.blocked_reasons_count.items() if v > 0]
    
    has_fail = any(g.status == "FAIL" for g in gates)
    has_improve = any(g.status == "IMPROVE" for g in gates)
    
    decision_action = "SKIP" # Default to safe skip
    verdict = "PASS" # Placeholder
    
    # Decision Hierarchy
    
    if scorecard.kill_switch_triggered:
        decision_action = "BLOCK"
        verdict = "FAIL"
        blocked_reasons.append("KILL_SWITCH_ACTIVE")
        
    elif has_improve or (scorecard.blocked_count > 0): # Explicit RISK FAIL mapping
        decision_action = "BLOCK"
        verdict = "FAIL" # User requested BLOCK => FAIL
        # Note: 'has_improve' usually comes from RISK_OK gate being IMPROVE
        
    elif has_fail: 
        # e.g. SNIPER_CERT_OK=FAIL
        # If the FAIL is due to Cert Missing, we want decision=SKIP based on user request ("Cert Missing -> SKIP")
        # But user also said "decision=SKIP => verdict=IMPROVE". 
        # And "decision=BLOCK => verdict=FAIL".
        # Let's check reasons.
        is_cert_fail = any(g.gate_id == "SNIPER_CERT_OK" and g.status == "FAIL" for g in gates)
        is_evidence_fail = any(g.gate_id == "POOL_EVIDENCE_OK" and g.status == "FAIL" for g in gates)
        
        if is_cert_fail and not is_evidence_fail:
             decision_action = "SKIP"
             verdict = "IMPROVE" # As per user mapping SKIP -> IMPROVE (or PASS idle? User said "verdict MUST be IMPROVE" for SKIP)
        else:
             decision_action = "BLOCK" # Evidence missing or other failures
             verdict = "FAIL"
             
    elif scorecard.planned_orders > 0:
        decision_action = "ALLOW"
        verdict = "PASS"
        
    else:
        # No failures, no blocks, but NO ORDERS (Idle)
        decision_action = "SKIP"
        verdict = "IMPROVE" # User: "Idle 'PASS' olmayacak... SKIP -> IMPROVE map"
    
    # Build summary
    gate_statuses = [f"{g.gate_id}={g.status}" for g in gates]
    summary = f"{decision_action} ({verdict}) | Gates: {', '.join(gate_statuses)}"
    
    stats = {
        "intents_created": scorecard.intents_created,
        "selected_count": scorecard.selected_count,
        "blocked_count": scorecard.blocked_count,
        "planned_orders": scorecard.planned_orders
    }
    
    return PoolCourtVerdictV1(
        run_id=scorecard.run_id,
        stage=scorecard.stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        decision_action=decision_action,
        verdict=verdict,
        gates=gates,
        summary=summary,
        blocked_reasons=blocked_reasons,
        skipped_reasons=skipped_reasons,
        stats=stats,
        suggested_actions=suggested_actions,
        evidence_paths=evidence_paths or {}
    )
