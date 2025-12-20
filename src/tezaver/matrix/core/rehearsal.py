import os
import json
import time
from typing import Dict, Optional
from tezaver.matrix.core.checksums import write_json

def run_rehearsal(home: str, candidate_id: Optional[str] = None) -> Dict:
    checks = []
    fail_codes = []
    
    def add_check(code, name, passed, detail=""):
        status = "PASS" if passed else "FAIL"
        checks.append({"code": code, "name": name, "status": status, "detail": detail})
        if not passed:
            fail_codes.append(code)
            
    # Determine Broker Mode for relaxed checks
    broker_mode = "PAPER"
    bc_path = os.path.join(home, "cloud_runtime", "broker_config.json")
    if os.path.exists(bc_path):
        try:
            with open(bc_path) as f: bc = json.load(f)
            broker_mode = bc.get("mode", "PAPER")
        except: pass
    is_real = broker_mode.startswith("REAL")
    
    # RH-01: Release Gate PASS
    rh01_pass = False
    rh01_detail = "No candidate specified"
    if candidate_id:
        from tezaver.matrix.core.release_gate import evaluate_release_gate
        gate = evaluate_release_gate(home, candidate_id)
        rh01_pass = gate.get("ok", False)
        rh01_detail = gate.get("summary", "")
    add_check("RH-01", "Release Gate PASS", rh01_pass, rh01_detail)
    
    # RH-02: Migration OK
    mig_path = os.path.join(home, "ops", "migration", "latest.json")
    rh02_pass = False
    rh02_detail = "No migration report"
    if os.path.exists(mig_path):
        try:
            with open(mig_path) as f: mig = json.load(f)
            fail_count = mig.get("fail", 0)
            rh02_pass = fail_count == 0
            rh02_detail = f"OK:{mig.get('ok',0)}, Fail:{fail_count}, Skip:{mig.get('skipped',0)}"
        except: pass
    add_check("RH-02", "Migration OK", rh02_pass, rh02_detail)
    
    # RH-03: Ops Health GREEN
    health_path = os.path.join(home, "ops", "health", "latest.json")
    rh03_pass = False
    rh03_detail = "No health report"
    if os.path.exists(health_path):
        try:
            with open(health_path) as f: h = json.load(f)
            rh03_pass = h.get("overall") == "GREEN"
            rh03_detail = h.get("summary", "")
        except: pass
    add_check("RH-03", "Ops Health GREEN", rh03_pass, rh03_detail)
    
    # RH-04: No CRIT Alerts
    alerts_dir = os.path.join(home, "alerts", "active")
    crit_count = 0
    if os.path.exists(alerts_dir):
        for f in os.listdir(alerts_dir):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(alerts_dir, f)) as af: al = json.load(af)
                    if al.get("level") in ["CRITICAL", "CRIT", "BLOCK"]:
                        crit_count += 1
                except: pass
    rh04_pass = crit_count == 0
    add_check("RH-04", "No CRIT Alerts", rh04_pass, f"{crit_count} critical alerts active")
    
    # RH-05: Global Pause OFF
    gr_path = os.path.join(home, "cloud_runtime", "global_risk.json")
    paused = False
    if os.path.exists(gr_path):
        try:
            with open(gr_path) as f: gr = json.load(f)
            paused = gr.get("paused", False)
        except: pass
    rh05_pass = not paused
    add_check("RH-05", "Global Pause OFF", rh05_pass, "PAUSED" if paused else "OK")
    
    # RH-06: Secrets Present (relaxed in PAPER)
    from tezaver.matrix.core.secrets import load_binance_secrets
    sec = load_binance_secrets(home)
    secrets_present = sec.get("present", False)
    if is_real:
        rh06_pass = secrets_present
        rh06_detail = "Required for REAL mode"
    else:
        rh06_pass = True  # Relaxed
        rh06_detail = "Not required for PAPER mode" if not secrets_present else "OK"
    add_check("RH-06", "Secrets Present", rh06_pass, rh06_detail)
    
    # RH-07: UserStream Connected (relaxed in PAPER)
    us_path = os.path.join(home, "cloud_runtime", "userstream", "status.json")
    us_connected = False
    if os.path.exists(us_path):
        try:
            with open(us_path) as f: us = json.load(f)
            us_connected = us.get("status") in ["CONNECTED", "CONNECTED_WS"]
        except: pass
    if is_real:
        rh07_pass = us_connected
        rh07_detail = "Required for REAL mode"
    else:
        rh07_pass = True  # Relaxed
        rh07_detail = "Not required for PAPER mode" if not us_connected else "OK"
    add_check("RH-07", "UserStream Connected", rh07_pass, rh07_detail)
    
    # RH-08: Cloud Loop Last 3 Ticks OK
    loop_state_path = os.path.join(home, "cloud_loop", "state.json")
    loop_hist_path = os.path.join(home, "cloud_loop", "history.ndjson")
    tick_count = 0
    recent_fail = False
    if os.path.exists(loop_state_path):
        try:
            with open(loop_state_path) as f: ls = json.load(f)
            tick_count = ls.get("tick_count", 0)
        except: pass
    if os.path.exists(loop_hist_path):
        try:
            with open(loop_hist_path) as f: lines = f.readlines()[-10:]  # Last 10 events
            for l in lines:
                e = json.loads(l)
                if e.get("kind") == "LOOP_TICK_FAIL":
                    recent_fail = True
                    break
        except: pass
    rh08_pass = tick_count >= 3 and not recent_fail
    rh08_detail = f"Ticks: {tick_count}, Recent Fail: {recent_fail}"
    add_check("RH-08", "Cloud Loop 3+ Ticks OK", rh08_pass, rh08_detail)
    
    # Overall
    go = len(fail_codes) == 0
    
    report = {
        "ts": int(time.time()),
        "go": go,
        "overall": "GO" if go else "NO_GO",
        "checks": checks,
        "fail_codes": fail_codes,
        "summary": "All checks passed. Ready for production." if go else f"Blocked by: {', '.join(fail_codes)}"
    }
    
    return report

def write_latest(home: str, report: Dict) -> str:
    path = os.path.join(home, "ops", "rehearsal", "latest.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_json(path, report)
    return path
