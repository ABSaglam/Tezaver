import os
import json
from typing import Dict, List, Optional
from tezaver.matrix.core.checksums import sha256_file
from tezaver.matrix.core.cloud_import import read_export_manifest

def evaluate_release_gate(home: str, candidate_id: str, active_stage: Optional[str] = None) -> Dict:
    """
    MX-5190: Evaluates if a candidate is ready for release based on stage-specific gates and safety registry.
    """
    import os
    from tezaver.matrix.protocols.safety_registry import SafetyProtocolRegistry, SafetyStatus
    
    # 1. Determine active stage
    assumed_stage = False
    if not active_stage:
        active_stage = os.getenv("TEZAVER_STAGE")
    if not active_stage:
        active_stage = "WAR"
        assumed_stage = True
        
    checks = []
    blocking_protocols = []
    warnings = []
    
    def add_check(code, name, passed, detail="", severity="CRITICAL"):
        status = "PASS" if passed else "FAIL"
        checks.append({
            "code": code,
            "name": name,
            "status": status,
            "detail": detail,
            "severity": severity
        })
        if not passed:
            if severity == "CRITICAL":
                blocking_protocols.append(code)  # Use MX code for clarity
            else:
                warnings.append(code)


    # RG-00: Safety Registry Check (MX-5260 integration)
    try:
        registry = SafetyProtocolRegistry()
        for p in registry.protocols:
            status = registry.get_overall_for_active(p["mx"], active_stage)
            
            # Check for existing run to validate run-scoped evidence
            # This is tricky because evaluate_release_gate is often called standalone.
            # We'll try to find a representative run if not provided.
            latest_run_dir = None
            runs = find_runs("WAR") + find_runs("SNIPER") + find_runs("LIVE")
            if runs:
                # Find run for this specific candidate
                cand_runs = [r for r in runs if r.get("run_id")]
                if cand_runs:
                    latest_run_dir = os.path.join(home, "out", "matrix_runs", cand_runs[0]["meta"].get("run_profile", "war").lower(), cand_runs[0]["run_id"])

            drift = registry.check_evidence(p["mx"], latest_run_dir)
            evidence_missing = any(drift.values())

            if status == SafetyStatus.RED:
                add_check(p["mx"], p["name"], False, f"Safety Protocol {p['mx']} is RED for {active_stage}", "CRITICAL")
            elif status in [SafetyStatus.YELLOW, SafetyStatus.GRAY]:
                add_check(p["mx"], p["name"], False, f"Safety Protocol {p['mx']} is {status.name} for {active_stage}", "WARNING")
            elif evidence_missing:
                missing_summary = ", ".join([f"{k}:{v}" for k, v in drift.items() if v])
                add_check(p["mx"], p["name"], False, f"Evidence Drift: Missing {missing_summary}", "WARNING")
            else:
                add_check(p["mx"], p["name"], True, f"Safety Protocol {p['mx']} is GREEN")
    except Exception as e:
        add_check("SR-FAIL", "Safety Registry Connection", False, str(e), "CRITICAL")


    # --- Helper: Find Runs ---
    def find_runs(profile: str) -> List[Dict]:
        matches = []
        # Support both 'runs' and 'out/matrix_runs/<profile>'
        base_dirs = [
            os.path.join(home, "runs"),
            os.path.join(home, "out", "matrix_runs", profile.lower())
        ]
        
        for runs_dir in base_dirs:
            if not os.path.exists(runs_dir): continue
            for rid in os.listdir(runs_dir):
                rdir = os.path.join(runs_dir, rid)
                if not os.path.isdir(rdir): continue
                m_path = os.path.join(rdir, "meta.json")
                j_path = os.path.join(rdir, "judge.json")
                report_path = os.path.join(rdir, "report.json")
                
                # Try meta.json or report.json
                meta = {}
                if os.path.exists(m_path):
                    with open(m_path) as f: meta = json.load(f)
                elif os.path.exists(report_path):
                    with open(report_path) as f: meta = json.load(f)
                
                if meta:
                    # Check profile (case insensitive)
                    if meta.get("run_profile", "").upper() == profile.upper() or \
                       profile.lower() in rdir.lower():
                        
                        found_id = meta.get("candidate", {}).get("candidate_id") or \
                                   meta.get("plan", {}).get("candidate_id")
                                   
                        if found_id == candidate_id:
                            judge = {}
                            if os.path.exists(j_path):
                                with open(j_path) as f: judge = json.load(f)
                            elif meta.get("verdict"): # WarEngine v2 style
                                judge = {"overall": meta.get("verdict")}
                                
                            matches.append({"meta": meta, "judge": judge, "run_id": rid})
        return matches

    # RG-01: SNIPER PASS
    sniper_runs = find_runs("SNIPER")
    sniper_passed = any(r["judge"].get("overall") == "PASS" for r in sniper_runs)
    add_check("RG-01", "Sniper PASS", sniper_passed, "Found passing Sniper run" if sniper_passed else "No passing Sniper run")
    
    # RG-02: WAR PASS
    war_runs = find_runs("WAR")
    war_passed = any(r["judge"].get("overall") == "PASS" for r in war_runs)
    add_check("RG-02", "War PASS", war_passed, "Passed War Game" if war_passed else "No passing War run")
    
    # RG-03: LIVE APPROVED
    live_runs = find_runs("LIVE")
    live_passed = False
    for r in live_runs:
        if r["judge"].get("overall") == "PASS":
            st_path = os.path.join(home, "candidates_stage", f"{candidate_id}.json")
            if os.path.exists(st_path):
                 with open(st_path) as f: st_data = json.load(f)
                 if st_data.get("stage") == "APPROVED":
                     live_passed = True
                     break
    add_check("RG-03", "Live APPROVED", live_passed, "Passed Live Run & Approved" if live_passed else "No approved Live Run")

    # Summary
    all_ok = all(c["status"] == "PASS" for c in checks if c["severity"] == "CRITICAL")
    
    return {
        "candidate_id": candidate_id,
        "active_stage": active_stage,
        "assumed_stage": assumed_stage,
        "ok": all_ok,
        "checks": checks,
        "blocking_protocols": blocking_protocols,
        "warnings": warnings,
        "summary": "Ready for Release" if all_ok else f"Release Blocked by {len(blocking_protocols)} critical issues"
    }

