"""
MX-5270: Safety Sweep - Automated verification of all protocols for a specific stage.
Calculates effective_status based on registry status + evidence drift.
"""
from typing import Dict, List, Optional
from tezaver.matrix.protocols.safety_registry import SafetyProtocolRegistry, SafetyStatus

def run_safety_sweep(run_dir: str, active_stage: str) -> Dict:
    """
    Perform a comprehensive safety sweep for the active stage.
    Tr: Aktif stage için tüm protokollerin kanıt ve durum kontrolünü yapar.
    """
    registry = SafetyProtocolRegistry()
    protocols_evaluated = []
    
    counts = {
        "GREEN": 0,
        "YELLOW": 0,
        "RED": 0,
        "GRAY": 0,
        "LOCKED": 0
    }
    
    blockers = []
    warnings = []
    
    for p in registry.protocols:
        mx = p["mx"]
        name = p["name"]
        
        # MX-5280: Skip protocols not active in current stage
        active_in = p.get("active_in", [])
        if active_stage not in active_in:
            continue  # Skip this protocol for this stage
        
        # Get declared status for this stage
        declared_status = registry.compute_overall_status(mx, active_stage)
        
        # Run evidence drift check
        drift = registry.check_evidence(mx, run_dir)
        evidence_ok = not any(drift.values())

        
        # Compute effective status
        # If declared GREEN but evidence missing -> degrade to YELLOW
        # If RED -> remains RED
        effective_status = declared_status
        reason = ""
        
        if declared_status == SafetyStatus.GREEN and not evidence_ok:
            effective_status = SafetyStatus.YELLOW
            reason = "Evidence drift detected (missing proof)"
        elif declared_status == SafetyStatus.RED:
            reason = f"Safety protocol {mx} is RED"
        elif declared_status in [SafetyStatus.YELLOW, SafetyStatus.GRAY]:
            reason = f"Safety protocol {mx} is {declared_status.value}"
            
        counts[effective_status.value] += 1
        
        # Format missing summary
        missing_parts = []
        if drift.get("tests"): missing_parts.append(f"tests:{len(drift['tests'])}")
        if drift.get("artifacts"): missing_parts.append(f"artifacts:{len(drift['artifacts'])}")
        if drift.get("telemetry"): missing_parts.append(f"telemetry:{len(drift['telemetry'])}")
        missing_summary = ", ".join(missing_parts)
        
        item = {
            "mx": mx,
            "name": name,
            "declared_status": declared_status.value,
            "effective_status": effective_status.value,
            "evidence_ok": evidence_ok,
            "missing_summary": missing_summary,
            "reason": reason
        }
        
        if effective_status == SafetyStatus.RED:
            blockers.append(item)
        elif effective_status in [SafetyStatus.YELLOW, SafetyStatus.GRAY]:
            warnings.append(item)
            
        protocols_evaluated.append(item)
        
    # Overall Verdict
    # PASS only if 0 REDs
    verdict = "PASS" if counts["RED"] == 0 else "FAIL"
    
    
    # MX-Phase 0.2: Pool Evidence Check
    # This must be non-blocking for now if pool is not enabled.
    # Where to get pool_enabled? 
    # Option 1: Env var TEZAVER_POOL_ENABLED
    # Option 2: Check for markers in run_dir/meta.json or similar?
    # For NON-BREAKING implementation, let's default to looking for a specific marker file OR meta config.
    
    pool_enabled = False
    try:
        import os
        import json
        meta_path = os.path.join(run_dir, "meta.json")
        if os.path.exists(meta_path):
             with open(meta_path, 'r') as f:
                 meta = json.load(f)
                 # Check config or pool specific fields
                 if meta.get("config", {}).get("pool_enabled"):
                     pool_enabled = True
                 # Also check for pool report which implies pool was active
                 elif os.path.exists(os.path.join(run_dir, "reports", "pool_universe_report_v1.json")):
                     pool_enabled = True
    except:
        pass
        
    # Check Env var override
    import os
    if os.getenv("TEZAVER_POOL_ENABLED") == "1":
        pool_enabled = True

    # Use run_id from path or meta?
    # run_dir usually like .../run_id
    run_id = os.path.basename(run_dir)
    
    pool_evidence_result = registry.check_pool_evidence_contract(
        run_dir=run_dir,
        stage=active_stage,
        run_id=run_id,
        pool_enabled=pool_enabled
    )
    
    # If pool enabled and missing, add to warnings? Or just report it separately?
    # Request says: pool_enabled true and missing var ise: MISSING + warnings increment
    if pool_evidence_result["status"] == "MISSING":
        # We treat Missing Pool Evidence as a WARNING for now (Phase 0.2), 
        # later might become BLOCKER (RED).
        warnings.append({
            "mx": "POOL-CONTRACT",
            "name": "Pool Evidence Contract",
            "reason": f"Missing artifacts: {len(pool_evidence_result['missing_ids'])}",
            "details": pool_evidence_result["missing_ids"]
        })
        # Note: Do not increment 'counts' dict because this is not a protocol in the registry logic yet,
        # it's an auxiliary check.

    return {
        "verdict": verdict,
        "active_stage": active_stage,
        "counts": counts,
        "blockers": blockers,
        "warnings": warnings,
        "protocols": protocols_evaluated,
        "pool_evidence": pool_evidence_result
    }
