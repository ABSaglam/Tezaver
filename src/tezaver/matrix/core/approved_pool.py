import os
import json
import shutil
import time
from typing import Dict, Optional
from tezaver.matrix.core.checksums import sha256_file, write_json

def approved_dir(home: str, candidate_id: str) -> str:
    path = os.path.join(home, "approved", candidate_id)
    os.makedirs(path, exist_ok=True)
    return path

def promote_candidate_from_run(home: str, run_id: str) -> Dict:
    # 1. Load Artefacts
    run_dir = os.path.join(home, "runs", run_id)
    if not os.path.exists(run_dir):
        raise ValueError(f"Run dir not found: {run_dir}")
        
    def load_json(name):
        p = os.path.join(run_dir, name)
        if not os.path.exists(p): return {}
        with open(p) as f: return json.load(f)
        
    meta = load_json("meta.json")
    if not meta: raise ValueError("meta.json missing")
    
    judge = load_json("judge.json")
    verdict = judge.get("overall", "UNKNOWN")
    
    # 2. Check Rules
    run_profile = meta.get("run_profile", "UNKNOWN")
    if run_profile != "LIVE":
        raise ValueError(f"Run must be LIVE (got {run_profile})")
        
    if verdict != "PASS":
        raise ValueError(f"Run verdict must be PASS (got {verdict})")
        
    # Check Stage
    candidate_id = "UNKNOWN"
    # Try getting CID from meta candidate info or guess
    sym = meta.get("candidate", {}).get("symbol")
    tf = meta.get("candidate", {}).get("timeframe")
    
    # We need exact candidate ID.
    # Usually we can derive or look up.
    # Let's assume we can map back if we scan candidates or pass as arg?
    # The requirement says "promote... from run". 
    # Let's see if we can deduce from run ID or meta.
    # We can try to match symbol/timeframe in candidates dir?
    # Or rely on `candidates_stage` side effect if written?
    # Actually run_live uses a specific candidate path?
    # Let's require the caller or deduce.
    # If meta has `candidate.id`? No, schema v4-dev.
    
    # Let's assume candidate_id is derivable or we search candidates dir for matching build_ts
    build_ts = meta.get("candidate", {}).get("build_ts")
    
    # Scan candidates in home/candidates for matching sym/tf/build_ts
    found_cid = None
    candidates_dir = os.path.join(home, "candidates")
    if os.path.exists(candidates_dir):
        for f in os.listdir(candidates_dir):
            if f.endswith(".json"):
                try:
                    p = os.path.join(candidates_dir, f)
                    with open(p) as cf: c = json.load(cf)
                    if (c.get("symbol") == sym and 
                        c.get("timeframe") == tf and 
                        c.get("build_ts") == build_ts):
                        found_cid = f.replace(".json", "")
                        break
                except: pass
                
    if not found_cid:
        # Fallback: maybe run_id contains it? No, random.
        # Fallback: create ID from sym_tf_ts?
        # But we need to check STAGE.
        # The prompt says "approval stage == APPROVED".
        raise ValueError("Could not identify candidate ID from run meta match")
        
    candidate_id = found_cid
    
    # Check Stage File
    stage_path = os.path.join(home, "candidates_stage", f"{candidate_id}.json")
    if not os.path.exists(stage_path):
        raise ValueError("Stage file missing")
        
    with open(stage_path) as f: sobj = json.load(f)
    if sobj.get("stage") != "APPROVED":
        raise ValueError(f"Candidate stage is {sobj.get('stage')}, must be APPROVED")
        
    # 3. Proceed to Promote
    dest_dir = approved_dir(home, candidate_id)
    proofs_dir = os.path.join(dest_dir, "proofs")
    os.makedirs(proofs_dir, exist_ok=True)
    
    # Copy Candidate
    src_cand = os.path.join(candidates_dir, f"{candidate_id}.json")
    if os.path.exists(src_cand):
        shutil.copy(src_cand, os.path.join(dest_dir, "candidate.json"))
        
    # Copy Proofs
    def copy_run_file(src_name, dest_name):
        src = os.path.join(run_dir, src_name)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(proofs_dir, dest_name))
            
    copy_run_file("meta.json", "last_live_run_meta.json")
    copy_run_file("judge.json", "last_live_run_judge.json")
    copy_run_file("scorecard.json", "last_live_run_scorecard.json")
    copy_run_file("audit.json", "last_live_run_audit.json")
    
    # Incidents?
    # Find incidents for run_id
    incidents_dir = os.path.join(home, "incidents")
    last_inc = None
    if os.path.exists(incidents_dir):
        incs = [i for i in os.listdir(incidents_dir) if f"INC_{run_id}" in i]
        incs.sort(reverse=True)
        if incs:
            last_inc = incs[0]
            src = os.path.join(incidents_dir, last_inc, "manifest.json")
            if os.path.exists(src):
                shutil.copy(src, os.path.join(proofs_dir, "last_incident_manifest.json"))
                
    # Data Report?
    dr_path = os.path.join(home, "data_reports", "latest.json")
    if os.path.exists(dr_path):
        shutil.copy(dr_path, os.path.join(proofs_dir, "data_report_latest.json"))
        
    # Generate Manifest
    # Calculate checksums of all files in dest_dir (recursive)
    checksums = {}
    for root, dirs, files in os.walk(dest_dir):
        for f in files:
            if f == "manifest.json": continue
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, dest_dir)
            checksums[rel] = sha256_file(fp)
            
    manifest = {
        "candidate_id": candidate_id,
        "symbol": sym,
        "timeframe": tf,
        "approved_ts": int(time.time()),
        "last_live_run_id": run_id,
        "trace": meta.get("trace", {}),
        "checksums": checksums
    }
    
    write_json(os.path.join(dest_dir, "manifest.json"), manifest)
    
    return {
        "candidate_id": candidate_id,
        "approved_path": dest_dir,
        "last_live_run_id": run_id
    }
