import os
import json
import shutil
import time
from typing import Optional

def build_incident_bundle(home: str, 
                          run_id: str, 
                          reason: str, 
                          max_events: int = 200, 
                          candidate_id: Optional[str] = None) -> str:
    """Creates a diagnostic bundle for a failed/blocked run."""
    
    timestamp = int(time.time())
    incident_id = f"INC_{run_id}_{timestamp}"
    
    incidents_dir = os.path.join(home, "incidents")
    bundle_dir = os.path.join(incidents_dir, incident_id)
    os.makedirs(bundle_dir, exist_ok=True)
    
    run_dir = os.path.join(home, "runs", run_id)
    included_files = []
    
    # 1. Copy Run Files
    for fname in ["meta.json", "gates.json", "audit.json"]:
        src = os.path.join(run_dir, fname)
        if os.path.exists(src):
            shutil.copy(src, bundle_dir)
            included_files.append(fname)
            
    # 2. Tail Events
    events_src = os.path.join(run_dir, "events.ndjson")
    if os.path.exists(events_src):
        # Read all, take last N
        with open(events_src, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        tail_lines = lines[-max_events:] if len(lines) > max_events else lines
        
        with open(os.path.join(bundle_dir, "events_tail.ndjson"), "w", encoding="utf-8") as f:
            f.writelines(tail_lines)
            
        included_files.append("events_tail.ndjson")
        
    # 3. Diagnostics Report (Global Latest)
    diag_src = os.path.join(home, "data_reports", "latest.json")
    if os.path.exists(diag_src):
        shutil.copy(diag_src, os.path.join(bundle_dir, "diagnostics_latest.json"))
        included_files.append("diagnostics_latest.json")
        
    # 4. Candidate Snapshot (if ID provided)
    if candidate_id:
        cand_src = os.path.join(home, "candidates", f"{candidate_id}.json")
        # Retry with .tezaver_matrix logic if home is not enough? 
        # Usually home/candidates is correct per Phase-1
        if os.path.exists(cand_src):
             shutil.copy(cand_src, os.path.join(bundle_dir, f"candidate_{candidate_id}.json"))
             included_files.append(f"candidate_{candidate_id}.json")

    # 5. Write Manifest
    manifest = {
        "incident_id": incident_id,
        "run_id": run_id,
        "reason": reason,
        "created_ts": timestamp,
        "included_files": included_files
    }
    with open(os.path.join(bundle_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    return incident_id
