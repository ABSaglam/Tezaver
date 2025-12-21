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
    
    return {
        "verdict": verdict,
        "active_stage": active_stage,
        "counts": counts,
        "blockers": blockers,
        "warnings": warnings,
        "protocols": protocols_evaluated
    }
