import os
import json
from typing import Dict, List, Optional
from tezaver.matrix.core.checksums import sha256_file
from tezaver.matrix.core.cloud_import import read_export_manifest

def evaluate_release_gate(home: str, candidate_id: str) -> Dict:
    checks = []
    
    # --- Check Helper ---
    def add_check(code, name, passed, detail=""):
        checks.append({
            "code": code,
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "detail": detail
        })
        
    # --- Helper: Find Runs ---
    def find_runs(profile: str) -> List[Dict]:
        matches = []
        runs_dir = os.path.join(home, "runs")
        if not os.path.exists(runs_dir): return []
        
        for rid in os.listdir(runs_dir):
            rdir = os.path.join(runs_dir, rid)
            m_path = os.path.join(rdir, "meta.json")
            j_path = os.path.join(rdir, "judge.json")
            
            if os.path.exists(m_path):
                try:
                    with open(m_path) as f: meta = json.load(f)
                    # Check profile
                    if meta.get("run_profile") == profile:
                        # Check candidate (meta schema v4-dev usually has candidate obj or we match symbol/tf/ts)
                        # Let's assume meta["candidate"]["id"] or derivation.
                        # For now, simplistic: match if we can confirm candidate_id (from build_ts etc.)
                        # Optimization: pass explicit candidate_id in meta if possible.
                        # As per Phase-9A, run meta has `candidate` dict.
                        # We might need to match attributes if ID not explicit.
                        # Let's assume ID is in meta or we check files.
                        
                        # Simplified check: we look for explicit ID or match by assumption
                        # For robustness, we assume run system tags candidate ID or we search.
                        # In the test fixture we will ensure meta matches expectation.
                        
                        # Assuming meta.get("candidate", {}).get("id") == candidate_id
                        # Or checking if candidate json file inside run matches?
                        
                        found_id = meta.get("candidate", {}).get("candidate_id")
                        if not found_id:
                             # Try "id" field
                             found_id = meta.get("candidate", {}).get("id")
                             
                        if found_id == candidate_id:
                            judge = {}
                            if os.path.exists(j_path):
                                with open(j_path) as f: judge = json.load(f)
                            matches.append({"meta": meta, "judge": judge})
                except: pass
        return matches

    # RG-01: SNIPER PASS
    # Find any run with profile=SNIPER, candidate=cid, judge=PASS
    sniper_passed = False
    sniper_runs = find_runs("SNIPER")
    for r in sniper_runs:
        if r["judge"].get("overall") == "PASS":
            sniper_passed = True
            break
            
    add_check("RG-01", "Sniper PASS", sniper_passed, "Found passing Sniper run" if sniper_passed else "No passing Sniper run found")
    
    # RG-02: WAR PASS
    # Check war_sessions
    war_passed = False
    war_dir = os.path.join(home, "war_sessions")
    # Simplified: Scan sessions for candidate participation and non-fail
    # This might be heavy if many sessions.
    # In V4, we might just look for a "war_proof.json" in candidate dir? Not in prompt.
    # We scan sessions.
    if os.path.exists(war_dir):
        for sid in os.listdir(war_dir):
            if war_passed: break
            # Look for session report or index
            # Assume session_manifest.json or report.json
            # Or scan subdirs?
            # Prompt says "v0: session index'de per-candidate verdict PASS"
            # We'll just look for ANY session folder that implies success (mockable)
            # Or dedicated index file?
            # Let's verify via "war_sessions/<sid>/report.json"
            rp = os.path.join(war_dir, sid, "report.json")
            if os.path.exists(rp):
                with open(rp) as f: rep = json.load(f)
                # Check results
                for res in rep.get("results", []):
                    if res.get("candidate_id") == candidate_id and res.get("verdict") == "PASS":
                        war_passed = True
                        break
                        
    add_check("RG-02", "War PASS", war_passed, "Passed War Game" if war_passed else "No passing War Session found")
    
    # RG-03: LIVE APPROVED
    # Find active Run with profile=LIVE, candidate=cid, stage=APPROVED?
    # Actually, approval happens AFTER live run.
    # The requirement: "profile=LIVE and candidate_id matches run; approval stage == APPROVED + judge PASS"
    # Wait, usually Stage=APPROVED implies Live Run Passed.
    # But we check run explicitly.
    live_passed = False
    live_runs = find_runs("LIVE")
    for r in live_runs:
        # Check Stage file?
        # Prompt says "stage == APPROVED + judge PASS".
        # Stage is stored in candidates_stage/cid.json, separate from run.
        # But we need to link run to candidate.
        if r["judge"].get("overall") == "PASS":
            # Check stage
            st_path = os.path.join(home, "candidates_stage", f"{candidate_id}.json")
            if os.path.exists(st_path):
                 with open(st_path) as f: st = json.load(f)
                 if st.get("stage") == "APPROVED":
                     live_passed = True
                     break
                     
    add_check("RG-03", "Live APPROVED", live_passed, "Passed Live Run & Approved" if live_passed else "No approved Live Run")
    
    # RG-04: Approved Pool
    pool_path = os.path.join(home, "approved", candidate_id, "manifest.json")
    in_pool = os.path.exists(pool_path)
    add_check("RG-04", "Approved Pool", in_pool, "Manifest exists" if in_pool else "Not in approved pool")
    
    # RG-05: Export Exists
    # Scan exports for candidate_id in manifest
    export_exists = False
    last_export_path = None
    exports_dir = os.path.join(home, "exports")
    if os.path.exists(exports_dir):
        # Scan dirs starting with EXPORT_candidate_id?
        # Naming convention: EXPORT_{cid}_{ts}
        prefix = f"EXPORT_{candidate_id}_"
        for d in os.listdir(exports_dir):
            if d.startswith(prefix):
                # Verify manifest
                mp = os.path.join(exports_dir, d, "export_manifest.json")
                if os.path.exists(mp):
                    export_exists = True
                    last_export_path = os.path.join(exports_dir, d)
                    # We pick one (latest?) - any valid exist is enough for RG-05
                    # But RG-06 needs checks.
                    break
                    
    add_check("RG-05", "Export Exists", export_exists, "Export package found" if export_exists else "No export package")
    
    # RG-06: Cloud Import Ready (Checksums)
    # If export exists, verify it.
    import_ready = False
    detail = "No export to verify"
    if export_exists and last_export_path:
        try:
             # Basic manual check or reuse verification logic
             # We should probably call verify_export_manifest logic if possible, 
             # but to avoid circ dep or overhead, repeat minimal check
             with open(os.path.join(last_export_path, "export_manifest.json")) as f:
                 man = json.load(f)
                 
             # Check checksums
             valid_sha = True
             for frel, exp_sha in man.get("sha256", {}).items():
                 fp = os.path.join(last_export_path, frel)
                 if not os.path.exists(fp) or sha256_file(fp) != exp_sha:
                     valid_sha = False
                     detail = f"Checksum fail: {frel}"
                     break
                     
             if valid_sha:
                 import_ready = True
                 detail = "Package Verified"
        except Exception as e:
            detail = str(e)
            
    add_check("RG-06", "Cloud Import Ready", import_ready, detail)
    
    # Summary
    all_ok = all(c["status"] == "PASS" for c in checks)
    
    return {
        "candidate_id": candidate_id,
        "ok": all_ok,
        "checks": checks,
        "summary": "Ready for Release" if all_ok else "Release Blocked"
    }
