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

def advance_stage_on_pass(current_stage: str, run_profile: str) -> str:
    # Logic: 
    # SNIPER passes -> move to WAR (if currently NEW or SNIPER)
    # WAR passes -> move to LIVE (if currently WAR)
    # LIVE passes -> move to APPROVED (if currently LIVE)
    
    # Allow advancement only if profile matches current stage context or we assume profile dictates target?
    # Prompt: "SNIPER PASS -> WAR", "WAR PASS -> LIVE", "LIVE PASS -> APPROVED"
    # What if we run SNIPER on a LIVE stage candidate? Should it demote? No.
    # What if we run LIVE on a NEW candidate? Should it jump? 
    # Let's be strict or loose?
    # Loose: If profile SNIPER and pass, ensure at least WAR.
    # But usually sequential.
    
    target = current_stage
    if run_profile == "SNIPER":
        target = "WAR"
    elif run_profile == "WAR":
        target = "LIVE"
    elif run_profile == "LIVE":
        target = "APPROVED"
        
    # Prevent demotion if already higher?
    # Stages order: NEW < SNIPER < WAR < LIVE < APPROVED
    ranks = {"NEW":0, "SNIPER":1, "WAR":2, "LIVE":3, "APPROVED":4}
    if ranks.get(target, 0) > ranks.get(current_stage, 0):
        return target
    return current_stage

def apply_run_result(home: str, run_id: str, judge_dict: Dict, candidate_id: str, run_profile: str) -> Dict:
    """Updates candidate stage based on judge verdict and run profile."""
    
    current = get_candidate_stage(home, candidate_id)
    stage = current["stage"]
    flags = current.get("flags", {})
    
    verdict = judge_dict["overall"]
    
    if verdict == "PASS":
        # Advance based on profile
        stage = advance_stage_on_pass(stage, run_profile)
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
