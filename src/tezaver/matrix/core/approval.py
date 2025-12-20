import os
import json
import time
from typing import Dict, Optional

STAGES = ["NEW", "SNIPER", "WAR", "LIVE", "APPROVED"]

def get_candidate_stage_path(home: str, candidate_id: str) -> str:
    d = os.path.join(home, "candidates_stage")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, f"{candidate_id}.json")

def get_candidate_stage(home: str, candidate_id: str) -> Dict:
    path = get_candidate_stage_path(home, candidate_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
            
    # Default
    return {
        "candidate_id": candidate_id,
        "stage": "NEW",
        "last_run_id": "",
        "updated_ts": int(time.time()),
        "flags": {}
    }

def set_candidate_stage(home: str, candidate_id: str, stage: str, last_run_id: str, flags: Dict) -> None:
    data = {
        "candidate_id": candidate_id,
        "stage": stage,
        "last_run_id": last_run_id,
        "updated_ts": int(time.time()),
        "flags": flags
    }
    path = get_candidate_stage_path(home, candidate_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def advance_stage_on_pass(current_stage: str) -> str:
    if current_stage == "NEW": return "SNIPER"
    if current_stage == "SNIPER": return "WAR"
    if current_stage == "WAR": return "LIVE"
    if current_stage == "LIVE": return "APPROVED"
    return "APPROVED" # Max

def apply_run_result(home: str, run_id: str, judge_dict: Dict, candidate_id: str) -> Dict:
    """Updates candidate stage based on judge verdict."""
    
    current = get_candidate_stage(home, candidate_id)
    stage = current["stage"]
    flags = current.get("flags", {})
    
    verdict = judge_dict["overall"]
    
    if verdict == "PASS":
        # Advance
        stage = advance_stage_on_pass(stage)
        flags["needs_fix"] = False
        flags["blocked"] = False
    elif verdict == "FAIL":
        # Block
        flags["blocked"] = True
    elif verdict == "IMPROVE":
        # Needs fix
        flags["needs_fix"] = True
        
    set_candidate_stage(home, candidate_id, stage, run_id, flags)
    
    return {
        "candidate_id": candidate_id,
        "stage": stage,
        "flags": flags
    }
