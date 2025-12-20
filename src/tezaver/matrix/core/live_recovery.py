import os
import json
import time
from typing import Dict, List

def recover_live_runs(home: str) -> Dict:
    runs_dir = os.path.join(home, "runs")
    if not os.path.exists(runs_dir):
        return {"runs_scanned": 0, "warnings": []}
        
    scanned = 0
    warnings = []
    
    for rid in os.listdir(runs_dir):
        r_dir = os.path.join(runs_dir, rid)
        if not os.path.isdir(r_dir): continue
        
        # Check if LIVE run
        ls_path = os.path.join(r_dir, "live_state.json")
        if os.path.exists(ls_path):
            scanned += 1
            
            # Check Critical Artifacts
            if not os.path.exists(os.path.join(r_dir, "meta.json")):
                warnings.append(f"Run {rid}: Missing meta.json")
                
            if not os.path.exists(os.path.join(r_dir, "events.ndjson")):
                 warnings.append(f"Run {rid}: Missing events.ndjson")
                 
            # Additional logic: Check if running but not in orchestrator?
            # That's cross-check, maybe for later.
            
    return {
        "runs_scanned": scanned,
        "warnings": warnings
    }
