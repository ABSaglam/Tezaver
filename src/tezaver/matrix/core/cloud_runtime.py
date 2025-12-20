import os
import json
import time
import uuid
from typing import List, Dict, Any

def list_active_strategies(home: str) -> List[str]:
    reg_dir = os.path.join(home, "cloud_registry", "strategies")
    if not os.path.exists(reg_dir):
        return []
    
    active = []
    for sid in os.listdir(reg_dir):
        s_dir = os.path.join(reg_dir, sid)
        if not os.path.isdir(s_dir): continue
        
        # Check status.json
        stat_path = os.path.join(s_dir, "status.json")
        if os.path.exists(stat_path):
            try:
                with open(stat_path) as f: s = json.load(f)
                if s.get("status") == "ACTIVE":
                    active.append(sid)
            except:
                pass
                
    return sorted(active)

def _ensure_runtime_dirs(home: str) -> str:
    r_dir = os.path.join(home, "cloud_runtime")
    os.makedirs(os.path.join(r_dir, "runs"), exist_ok=True)
    return r_dir

def start_or_load_runtime_state(home: str) -> Dict[str, Any]:
    r_dir = _ensure_runtime_dirs(home)
    state_path = os.path.join(r_dir, "state.json")
    
    if os.path.exists(state_path):
        with open(state_path) as f: return json.load(f)
        
    # Create new run
    run_id = f"CLOUDRUN_{int(time.time())}"
    state = {
        "cloud_run_id": run_id,
        "started_ts": int(time.time()),
        "last_tick_ts": 0,
        "total_ticks": 0
    }
    
    # Init run dir
    run_dir = os.path.join(r_dir, "runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump({"run_id": run_id, "type": "CLOUD_RUNTIME", "ts": int(time.time())}, f)
        
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)
        
    return state

def append_runtime_event(home: str, cloud_run_id: str, event: Dict[str, Any]) -> None:
    path = os.path.join(home, "cloud_runtime", "runs", cloud_run_id, "events.ndjson")
    with open(path, "a") as f:
        f.write(json.dumps(event) + "\n")

def cloud_runtime_tick(home: str, ticks: int = 1, steps_per_strategy: int = 10) -> Dict[str, Any]:
    state = start_or_load_runtime_state(home)
    crid = state["cloud_run_id"]
    
    active_strats = list_active_strategies(home)
    
    events_written = 0
    
    for t in range(ticks):
        tick_ts = int(time.time() * 1000)
        
        # 1. Process Strategies
        for sid in active_strats:
            # Dry Run: Just log a tick event
            evt = {
                "ts": tick_ts,
                "type": "CLOUD_TICK",
                "strategy_id": sid,
                "payload": {
                    "steps": steps_per_strategy,
                    "status": "HOLD", # Default dry run action
                    "message": "Dry run tick processed"
                }
            }
            append_runtime_event(home, crid, evt)
            events_written += 1
            
        # 2. Heartbeat
        hb = {
            "ts": tick_ts,
            "type": "RUNTIME_HEARTBEAT",
            "active_count": len(active_strats),
            "strategies": active_strats
        }
        append_runtime_event(home, crid, hb)
        
        # Update State
        state["last_tick_ts"] = int(time.time())
        state["total_ticks"] += 1
        
    # Save State
    with open(os.path.join(home, "cloud_runtime", "state.json"), "w") as f:
        json.dump(state, f, indent=2)
        
    # Save Heartbeat snapshot
    with open(os.path.join(home, "cloud_runtime", "runs", crid, "heartbeat.json"), "w") as f:
        json.dump(hb, f, indent=2)
        
    return {
        "cloud_run_id": crid,
        "ticks_processed": ticks,
        "events_written": events_written,
        "active_strategies": len(active_strats),
        "state": state
    }
