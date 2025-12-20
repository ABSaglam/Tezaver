import os
import json
import shutil
import time
from typing import Dict
from tezaver.matrix.core.checksums import sha256_file, write_json

def export_candidate(home: str, candidate_id: str, ts: int = None) -> Dict:
    approved_path = os.path.join(home, "approved", candidate_id)
    if not os.path.exists(approved_path):
        raise ValueError(f"Candidate not found in approved pool: {candidate_id}")
        
    ts = ts or int(time.time())
    export_id = f"EXPORT_{candidate_id}_{ts}"
    export_dir = os.path.join(home, "exports", export_id)
    os.makedirs(export_dir, exist_ok=True)
    
    # Copy everything from approved/<cid>
    # Recursive copy
    # shutil.copytree requires dest to not exist usually, but we made it.
    # Iterate and copy.
    
    # Helper recursive copy content
    files_list = []
    
    for root, dirs, files in os.walk(approved_path):
        # Determine relative path from approve root
        rel_dir = os.path.relpath(root, approved_path)
        dest_subdir = export_dir if rel_dir == "." else os.path.join(export_dir, rel_dir)
        os.makedirs(dest_subdir, exist_ok=True)
        
        for f in files:
            src_f = os.path.join(root, f)
            dest_f = os.path.join(dest_subdir, f)
            shutil.copy2(src_f, dest_f)
            files_list.append(os.path.relpath(dest_f, export_dir))
            
    # Read approved manifest to get base info
    man_path = os.path.join(approved_path, "manifest.json")
    if os.path.exists(man_path):
        with open(man_path) as f: man = json.load(f)
        sym = man.get("symbol")
        tf = man.get("timeframe")
        trace = man.get("trace")
    else:
        sym = "UNKNOWN"
        tf = "UNKNOWN"
        trace = {}
            
    # Calculate checksums for export package
    sha_map = {}
    for frel in files_list:
        sha_map[frel] = sha256_file(os.path.join(export_dir, frel))
        
    # Export Manifest
    export_manifest = {
        "version": "export_v1",
        "candidate_id": candidate_id,
        "symbol": sym,
        "timeframe": tf,
        "trace": trace,
        "created_ts": ts,
        "files": files_list,
        "sha256": sha_map
    }
    
    write_json(os.path.join(export_dir, "export_manifest.json"), export_manifest)
    
    return {
        "export_id": export_id,
        "export_path": export_dir,
        "manifest_path": os.path.join(export_dir, "export_manifest.json")
    }
