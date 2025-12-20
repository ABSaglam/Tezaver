import os
import json
import time
from typing import Dict, List
from tezaver.matrix.core.checksums import write_json

def get_recent_events(home: str, window_hours: int = 24) -> List[Dict]:
    events = []
    cutoff = (int(time.time()) - window_hours * 3600) * 1000 # ms for events?
    # Some systems use ms, some sec. Let's normalize. 
    # Cloud Runtime Events: ms (as per cloud_runtime.py)
    # Alert Events: ms? (alert_engine.py)
    
    def load_ndjson(path, source_type):
        if not os.path.exists(path): return
        with open(path) as f:
            for line in f:
                try:
                    e = json.loads(line)
                    ets = e.get("ts", 0)
                    # Normalize to ms if plausible (if ts < 3e10, likely sec)
                    if ets < 30000000000: ets *= 1000
                    
                    if ets > cutoff:
                        e["_source"] = source_type
                        e["ts"] = ets # normalized
                        events.append(e)
                except: pass

    # 1. Cloud Runtime Events (scan all active runs? or just latest?)
    # Ideally we scan recent runs.
    runs_dir = os.path.join(home, "cloud_runtime", "runs")
    if os.path.exists(runs_dir):
        # Sort by name (usually timestamped/uuid) - maybe scan all?
        # Optimization: scan last 5 runs
        rids = sorted(os.listdir(runs_dir))[-5:]
        for r in rids:
            load_ndjson(os.path.join(runs_dir, r, "events.ndjson"), "RUNTIME")
            
    # 2. Migration Ops
    load_ndjson(os.path.join(home, "ops", "migration", "events.ndjson"), "MIGRATION")
    
    # 3. UserStream Raw? Too heavy.
    # We rely on "USERSTREAM_CONNECTED" etc events if runtime tracks them?
    # Runtime emits "BROKER_TELEMETRY".
    # UserStream Reconciler emits "EXCHANGE_ORDER_UPDATE".
    # Let's rely on Runtime's "STRATEGY_RECONNECT" if implied, or just count RECONNECTs from logs if present.
    # Currently UserStreamRunner logs raw to raw.ndjson, maybe not useful here unless we parse specific msgs.
    # Let's skip raw for SLO, assume runtime events cover major issues.
    
    events.sort(key=lambda x: x.get("ts", 0))
    return events

def compute_slo(home: str, window_hours: int = 24) -> Dict:
    events = get_recent_events(home, window_hours)
    
    counts = {
        "cloud_ticks": 0,
        "gap_detected": 0,
        "reconnects": 0, # Inferred or explicit
        "risk_blocks": 0,
        "broker_misconfig": 0,
        "reduce_only_violations": 0,
        "alerts_created": 0 # Need separate scan or inclusion
    }
    
    for e in events:
        t = e.get("type", "")
        if t == "CLOUD_TICK_START": counts["cloud_ticks"] += 1
        if t == "STRATEGY_GAP_DETECTED": counts["gap_detected"] += 1
        if t == "GLOBAL_RISK_BLOCK": counts["risk_blocks"] += 1
        if t == "BROKER_MISCONFIG": counts["broker_misconfig"] += 1
        if t == "REDUCE_ONLY_VIOLATION": counts["reduce_only_violations"] += 1
        # Reconnects? If we have "BROKER_RECONNECT"? Not implemented yet in runtime.
        # But we can infer GAP? 
        
    # Scan Alerts creation separately? Or assume Alert Engine emits event.
    # Alert engine emits "ALERT_CREATED"? Checks alert_engine.py.
    # Alert Engine code: It saves to file.
    # We can scan active/history alerts for creation time.
    curr_ms = int(time.time() * 1000)
    cutoff_ms = curr_ms - (window_hours * 3600 * 1000)
    
    # Scan Alerts
    alert_counts = 0
    for subdir in ["active", "history"]:
        d = os.path.join(home, "alerts", subdir)
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".json"):
                    try:
                        with open(os.path.join(d, f)) as af: al = json.load(af)
                        if al.get("created_ts", 0) > cutoff_ms:
                            alert_counts += 1
                    except: pass
    counts["alerts_created"] = alert_counts

    return {
        "ts": int(time.time()),
        "window_hours": window_hours,
        "counts": counts,
        "summary": "SLO Computed"
    }

def compute_timeline(home: str, window_hours: int = 24) -> List[Dict]:
    events = get_recent_events(home, window_hours)
    timeline = []
    
    # Add Alerts
    curr_ms = int(time.time() * 1000)
    cutoff_ms = curr_ms - (window_hours * 3600 * 1000)
    for subdir in ["active", "history"]:
        d = os.path.join(home, "alerts", subdir)
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.endswith(".json"):
                    try:
                        with open(os.path.join(d, f)) as af: al = json.load(af)
                        if al.get("created_ts", 0) > cutoff_ms:
                            timeline.append({
                                "ts": al.get("created_ts"),
                                "kind": "ALERT",
                                "title": f"Alert [{al.get('level')}]",
                                "detail": al.get("message")
                            })
                    except: pass
                    
    # Format Runtime Events
    for e in events:
        t = e.get("type")
        if t in ["CLOUD_TICK_START", "BROKER_TELEMETRY"]: continue # Too noisy
        
        kind = "RUNTIME"
        if e.get("_source") == "MIGRATION": kind = "MIGRATION"
        
        title = t
        detail = str(e.get("payload") or e.get("detail") or "")
        
        timeline.append({
            "ts": e.get("ts"),
            "kind": kind,
            "title": title,
            "detail": detail
        })
        
    # Sort Reverse Chronological
    timeline.sort(key=lambda x: x["ts"], reverse=True)
    return timeline

def write_ops_reports(home: str, window_hours:24):
    slo = compute_slo(home, window_hours)
    tl = compute_timeline(home, window_hours)
    
    os.makedirs(os.path.join(home, "ops", "slo"), exist_ok=True)
    os.makedirs(os.path.join(home, "ops", "timeline"), exist_ok=True)
    
    write_json(os.path.join(home, "ops", "slo", "latest.json"), slo)
    write_json(os.path.join(home, "ops", "timeline", "latest.json"), tl)
