import os
import json
from typing import Dict
from collections import Counter

def compute_scorecard(home: str, run_id: str) -> Dict:
    """Computes a deterministic scorecard from run events."""
    
    events_path = os.path.join(home, "runs", run_id, "events.ndjson")
    if not os.path.exists(events_path):
        return {} # Should not happen in normal flow
        
    event_counts = Counter()
    bars_count = 0
    decisions_count = 0
    blocks_count = 0
    
    # Check incidents
    incidents_dir = os.path.join(home, "incidents")
    incidents_count = 0
    if os.path.exists(incidents_dir):
        # Count manifest files that match run_id
        # Heuristic: verify run_id inside manifest or directory name?
        # Directory name convention: INC_{run_id}_{ts}
        # Let's check directory names
        for dname in os.listdir(incidents_dir):
            if f"INC_{run_id}_" in dname:
                incidents_count += 1
    
    with open(events_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                ev = json.loads(line)
                etype = ev.get("event_type", "UNKNOWN")
                event_counts[etype] += 1
                
                if etype == "BAR" or etype == "CYCLE_STEP":
                     # CYCLE_STEP logic: one per bar
                     bars_count += 1
                
                if etype == "DECISION" or (etype == "CYCLE_STEP" and "decision" in ev.get("payload", {})):
                     decisions_count += 1
                     
                # Count explicit BLOCK events or blocked payload
                if etype == "BLOCK":
                    blocks_count += 1
                elif etype == "CYCLE_STEP":
                    if ev.get("payload", {}).get("blocked"):
                        blocks_count += 1
                        
            except:
                continue
                
    return {
        "run_id": run_id,
        "bars_count": bars_count,
        "decisions_count": decisions_count,
        "blocks_count": blocks_count,
        "incidents_count": incidents_count,
        "event_types": dict(event_counts)
    }
