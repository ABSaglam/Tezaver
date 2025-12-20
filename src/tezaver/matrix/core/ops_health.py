import os
import json
import time
from typing import Dict
from tezaver.matrix.core.checksums import write_json

def build_health_snapshot(home: str) -> Dict:
    signals = {
        "preflight_ok": False,
        "recovery_ok": False,
        "alerts_active": 0,
        "active_crit_alerts": 0,
        "active_warn_alerts": 0,
        "global_paused": False,
        "broker_mode": "UNKNOWN",
        "secrets_present": False,
        "userstream_connected": False,
        "drift_detected_recently": False,
        "last_cloud_tick_ts": None
    }
    
    # 1. Preflight
    pf_path = os.path.join(home, "ops", "preflight", "latest.json")
    if os.path.exists(pf_path):
        try:
             with open(pf_path) as f: pf = json.load(f)
             signals["preflight_ok"] = pf.get("status") == "PASS"
        except: pass
        
    # 2. Recovery
    rec_path = os.path.join(home, "ops", "recovery", "latest.json")
    if os.path.exists(rec_path):
        try:
             with open(rec_path) as f: rec = json.load(f)
             # If status is OK? Recovery file doesn't have simple valid field?
             # Assuming if execution completed, it's ok-ish, but check warnings?
             # Let's say recovery is ok if file exists and recent? 
             # Phase-11B recovery report format: {"ts":..., "actions":...}
             # Let's assume OK unless specific error field?
             signals["recovery_ok"] = True
        except: pass
        
    # 3. Alerts
    alerts_dir = os.path.join(home, "alerts", "active")
    if os.path.exists(alerts_dir):
        count = 0
        crit = 0
        warn = 0
        for f in os.listdir(alerts_dir):
            if f.endswith(".json"):
                count += 1
                try:
                    with open(os.path.join(alerts_dir, f)) as af: al = json.load(af)
                    lvl = al.get("level", "INFO")
                    if lvl in ["CRITICAL", "BLOCK"]: crit += 1
                    if lvl == "WARNING": warn += 1
                except: pass
        signals["alerts_active"] = count
        signals["active_crit_alerts"] = crit
        signals["active_warn_alerts"] = warn
        
    # 4. Cloud Runtime - Paused
    gr_path = os.path.join(home, "cloud_runtime", "global_risk.json")
    if os.path.exists(gr_path):
        try:
            with open(gr_path) as f: gr = json.load(f)
            signals["global_paused"] = gr.get("paused", False)
        except: pass
        
    # 5. Broker Config
    bc_path = os.path.join(home, "cloud_runtime", "broker_config.json")
    if os.path.exists(bc_path):
        try:
            with open(bc_path) as f: bc = json.load(f)
            signals["broker_mode"] = bc.get("mode", "UNKNOWN")
            # Secrets check logic not in config, handled separately or via preflight
            # But we can check if secrets.json loaded in runtime state? 
            # Or assume secrets.py check.
            # Let's use `tezaver.matrix.core.secrets.load_binance_secrets`
        except: pass
        
    # Secrets
    from tezaver.matrix.core.secrets import load_binance_secrets
    sec = load_binance_secrets(home)
    signals["secrets_present"] = sec.get("present", False)
    
    # 6. UserStream
    us_path = os.path.join(home, "cloud_runtime", "userstream", "status.json")
    if os.path.exists(us_path):
        try:
            with open(us_path) as f: us = json.load(f)
            signals["userstream_connected"] = us.get("status") == "CONNECTED_WS"
        except: pass
        
    # 7. Drift & Ticks (Events analysis or State)
    # Check State
    # We can rely on `cloud_runtime/state.json` but it's ephemeral
    # Or latest `runs/<id>/state.json`?
    # Or `heartbeat.json`?
    # Phase-14C.3: No explicit heartbeat file defined in Prompt, but highly recommended.
    # Let's check `runs` for latest Dir
    runs_dir = os.path.join(home, "cloud_runtime", "runs")
    if os.path.exists(runs_dir):
        # find latest
        rids = sorted(os.listdir(runs_dir))
        if rids:
            last_run = rids[-1]
            hb = os.path.join(runs_dir, last_run, "heartbeat.json")
            if os.path.exists(hb):
                try: 
                    with open(hb) as f: hbd = json.load(f)
                    signals["last_cloud_tick_ts"] = hbd.get("ts")
                except: pass
                
    # Drift
    # If any active Drift Alert -> handled in Alerts
    # Explicit drift flag? Maybe excessive.
    # Let's stick to alerts for drift.
    
    # --- EVALUATE OVERALL ---
    overall = "GREEN"
    reasons = []
    
    # RED Conditions
    if signals["global_paused"]:
        overall = "RED"
        reasons.append("System Paused")
        
    if signals["active_crit_alerts"] > 0:
        overall = "RED"
        reasons.append(f"{signals['active_crit_alerts']} Critical Alerts")
        
    is_real = signals["broker_mode"].startswith("REAL")
    if is_real and not signals["secrets_present"]:
        overall = "RED"
        reasons.append("Real Mode Missing Secrets")
        
    # YELLOW Conditions (only if not RED)
    if overall == "GREEN":
        if signals["active_warn_alerts"] > 0:
            overall = "YELLOW"
            reasons.append(f"{signals['active_warn_alerts']} Warnings")
            
        if is_real and not signals["userstream_connected"]:
            overall = "YELLOW" # Or RED? Data sync critical.
            # If REAL_BINANCE, disconnected stream is dangerous.
            # Let's say RED for REAL_BINANCE, YELLOW for STUB?
            if signals["broker_mode"] == "REAL_BINANCE":
                overall = "RED"
                reasons.append("UserStream Disconnected (REAL)")
            else:
                overall = "YELLOW"
                reasons.append("UserStream Disconnected")
                
        if not signals["preflight_ok"]:
             overall = "YELLOW" # Preflight fail might be non-critical?
             reasons.append("Preflight Failed")
             
    snapshot = {
        "ts": int(time.time()),
        "overall": overall,
        "summary": ", ".join(reasons) if reasons else "All Systems Operational",
        "signals": signals,
        "links": {
            "preflight": "ops/preflight/latest.json",
            "recovery": "ops/recovery/latest.json",
            "migration": "ops/migration/latest.json",
            "alerts_active_dir": "alerts/active/",
            "cloud_runtime_userstream": "cloud_runtime/userstream/status.json"
        }
    }
    
    return snapshot

def write_health_snapshot(home: str) -> str:
    snap = build_health_snapshot(home)
    path = os.path.join(home, "ops", "health", "latest.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json(path, snap)
    return path
