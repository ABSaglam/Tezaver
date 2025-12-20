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
    os.makedirs(os.path.join(r_dir, "strategies"), exist_ok=True)
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

def load_strategy_state(home: str, strategy_id: str) -> Dict[str, Any]:
    path = os.path.join(home, "cloud_runtime", "strategies", strategy_id, "state.json")
    if os.path.exists(path):
        with open(path) as f: return json.load(f)
    return None

def save_strategy_state(home: str, strategy_id: str, state: Dict[str, Any]) -> None:
    d = os.path.join(home, "cloud_runtime", "strategies", strategy_id)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "state.json"), "w") as f:
        json.dump(state, f, indent=2)
        
def parse_tf_ms(tf: str) -> int:
    # Minimal parser: 15m, 1h, 4h, 1d
    if tf.endswith("s"): return int(tf[:-1]) * 1000
    if tf.endswith("m"): return int(tf[:-1]) * 60 * 1000
    if tf.endswith("h"): return int(tf[:-1]) * 60 * 60 * 1000
    if tf.endswith("d"): return int(tf[:-1]) * 24 * 60 * 60 * 1000
    if tf == "1M": return 30 * 24 * 60 * 60 * 1000 # Approx
    return 15 * 60 * 1000 # Default fallback

def strategy_step(home: str, cloud_run_id: str, strategy_id: str, strategy_json: dict, steps: int) -> Dict[str, Any]:
    # 1. Check Bars Source
    bs = strategy_json.get("bars_source")
    if not bs or bs.get("type") != "JSON_FILE" or not bs.get("path"):
        evt = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_SKIPPED",
            "strategy_id": strategy_id, "payload": {"reason": "NO_BARS_SOURCE"}
        }
        append_runtime_event(home, cloud_run_id, evt)
        return {"skipped": True, "reason": "NO_BARS_SOURCE"}
        
    # 2. Load Bars
    b_path = bs["path"]
    if not os.path.exists(b_path):
        evt = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_SKIPPED",
            "strategy_id": strategy_id, "payload": {"reason": "BARS_FILE_MISSING", "path": b_path}
        }
        append_runtime_event(home, cloud_run_id, evt)
        return {"skipped": True, "reason": "BARS_FILE_MISSING"}
        
    try:
        with open(b_path) as f: bars = json.load(f)
    except Exception as e:
        evt = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_SKIPPED",
            "strategy_id": strategy_id, "payload": {"reason": "BARS_LOAD_ERROR", "error": str(e)}
        }
        append_runtime_event(home, cloud_run_id, evt)
        return {"skipped": True, "reason": "BARS_LOAD_ERROR"}
        
    # 3. Load State
    state = load_strategy_state(home, strategy_id)
    if not state:
        tf_ms = parse_tf_ms(strategy_json.get("timeframe", "15m"))
        state = {
            "cursor": 0,
            "last_ts": 0,
            "tf_ms": tf_ms,
            "bars_fingerprint": str(os.path.getmtime(b_path)) # Simple fingerpint for now
        }
        
    cursor = state["cursor"]
    last_ts = state["last_ts"]
    tf_ms = state["tf_ms"]
    
    # 4. Advance
    advanced = 0
    final_ts = int(time.time() * 1000)
    
    for _ in range(steps):
        if cursor >= len(bars): break
        
        bar = bars[cursor]
        if not bar.get("closed", False) and not bar.get("is_closed", False):
            # Bar not closed, assume it's current forming bar, maybe skip?
            # Or use it but don't advance cursor if we treat it as live?
            # For simplicity in 'playback' mode, we usually only ingest closed bars.
            # If we encounter an open bar in a JSON file, we probably stop there.
            break
            
        # Gap Check
        # If we have a last_ts, and (bar_ts - last_ts) > 1.1 * tf_ms
        bar_ts = bar["ts"]
        if last_ts > 0 and (bar_ts - last_ts) > (1.1 * tf_ms):
             evt = {
                "ts": int(time.time() * 1000), "type": "STRATEGY_GAP_DETECTED",
                "strategy_id": strategy_id,
                "payload": {"last_ts": last_ts, "current_ts": bar_ts, "delta": bar_ts - last_ts}
             }
             append_runtime_event(home, cloud_run_id, evt)
             
             evt_rec = {
                "ts": int(time.time() * 1000), "type": "STRATEGY_RECONNECT",
                "strategy_id": strategy_id, "payload": {}
             }
             append_runtime_event(home, cloud_run_id, evt_rec)
             
        # Bar Event
        evt_bar = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_BAR",
            "strategy_id": strategy_id,
            "payload": {"bar_ts": bar_ts, "close": bar["close"]}
        }
        append_runtime_event(home, cloud_run_id, evt_bar)
        
        # Decision (HOLD)
        evt_dec = {
            "ts": int(time.time() * 1000), "type": "STRATEGY_DECISION",
            "strategy_id": strategy_id,
            "payload": {"action": "HOLD", "bar_ts": bar_ts}
        }
        append_runtime_event(home, cloud_run_id, evt_dec)
        
        last_ts = bar_ts
        cursor += 1
        advanced += 1
        
    # 5. Heartbeat & Save
    state["cursor"] = cursor
    state["last_ts"] = last_ts
    save_strategy_state(home, strategy_id, state)
    
    evt_hb = {
        "ts": int(time.time() * 1000), "type": "STRATEGY_HEARTBEAT",
        "strategy_id": strategy_id,
        "payload": {"cursor": cursor, "total": len(bars), "last_ts": last_ts}
    }
    append_runtime_event(home, cloud_run_id, evt_hb)
    
    return {"skipped": False, "advanced": advanced, "cursor": cursor, "total": len(bars)}

def cloud_runtime_tick(home: str, ticks: int = 1, steps_per_strategy: int = 10) -> Dict[str, Any]:
    state = start_or_load_runtime_state(home)
    crid = state["cloud_run_id"]
    
    active_strats = list_active_strategies(home)
    
    events_written = 0
    strategy_results = {}
    
    for t in range(ticks):
        tick_ts = int(time.time() * 1000)
        
        # General Tick Event
        append_runtime_event(home, crid, {"ts": tick_ts, "type": "CLOUD_TICK", "tick_seq": state["total_ticks"] + 1})
        
        # Process Strategies
        for sid in active_strats:
            # Load Strategy JSON
            s_path = os.path.join(home, "cloud_registry", "strategies", sid, "strategy.json")
            if not os.path.exists(s_path):
                 # Can't run without def
                 continue
                 
            with open(s_path) as f: s_json = json.load(f)
            
            res = strategy_step(home, crid, sid, s_json, steps_per_strategy)
            strategy_results[sid] = res
            
        # Runtime Heartbeat
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
        "active_strategies": len(active_strats),
        "state": state,
        "latest_strategy_results": strategy_results
    }
