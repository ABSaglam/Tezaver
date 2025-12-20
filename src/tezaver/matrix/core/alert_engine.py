import os
import json
import time
import hashlib
from typing import Dict, Any, List, Optional
from tezaver.matrix.ports.notifier_port import NotifierPort
from tezaver.matrix.core.cloud_runtime import start_or_load_runtime_state

def scan_cloud_events_for_alerts(home: str, notifier: NotifierPort, cloud_run_id: Optional[str] = None) -> Dict[str, Any]:
    # 1. Resolve Run ID
    if not cloud_run_id:
        state = start_or_load_runtime_state(home)
        cloud_run_id = state.get("cloud_run_id")
        
    if not cloud_run_id:
        return {"scanned": 0, "new_alerts": 0, "error": "No active cloud run"}
        
    runs_dir = os.path.join(home, "cloud_runtime", "runs", cloud_run_id)
    events_path = os.path.join(runs_dir, "events.ndjson")
    
    if not os.path.exists(events_path):
        return {"scanned": 0, "new_alerts": 0, "error": "Events file not found"}
        
    # 2. Load Checkpoint
    chk_path = os.path.join(home, "alerts", "scan_state.json")
    checkpoint = {"last_line": 0, "run_id": cloud_run_id}
    if os.path.exists(chk_path):
        try:
            with open(chk_path) as f: 
                saved = json.load(f)
                if saved.get("run_id") == cloud_run_id:
                    checkpoint = saved
        except: pass
        
    start_line = checkpoint["last_line"]
    
    # 3. Scan
    new_alerts = 0
    current_line = 0
    
    with open(events_path, "r") as f:
        # Skip to start_line
        # Optimization: for huge files, seek usage is better but ndjson varying length makes line seeking hard without offsets.
        # Ideally we store byte offset. For now, simple line counting (Phase-13C scope).
        for i, line in enumerate(f):
            if i < start_line:
                current_line += 1
                continue
                
            try:
                evt = json.loads(line)
                alert = process_event(evt, cloud_run_id, i)
                if alert:
                    notifier.emit_alert(alert)
                    new_alerts += 1
            except:
                pass
            current_line += 1
            
    # 4. Save Checkpoint
    with open(chk_path, "w") as f:
        json.dump({"last_line": current_line, "run_id": cloud_run_id}, f)
        
    return {"scanned": current_line - start_line, "new_alerts": new_alerts, "cloud_run_id": cloud_run_id}

def process_event(evt: Dict[str, Any], run_id: str, line_no: int) -> Optional[Dict[str, Any]]:
    etype = evt.get("type")
    ts = evt.get("ts", int(time.time() * 1000))
    
    alert_type = None
    severity = "INFO"
    msg_tr = ""
    msg_en = ""
    dedup_suffix = ""
    
    if etype == "GLOBAL_RISK_BLOCK":
        # {"type": "GLOBAL_RISK_BLOCK", "payload": {"decision": "BUY", "reason": "...", "totals": ...}}
        alert_type = "RISK_BLOCK"
        severity = "WARN"
        p = evt.get("payload", {})
        reason = p.get("reason", "UNKNOWN")
        sid = evt.get("strategy_id", "GLOBAL")
        msg_tr = f"Risk Bloku: {sid} {p.get('decision')} engellendi. Sebep: {reason}"
        msg_en = f"Risk Block: {sid} {p.get('decision')} blocked. Reason: {reason}"
        dedup_suffix = f"{sid}:{reason}" # Basic dedup key part
        
    elif etype == "GLOBAL_PAUSED":
        alert_type = "PAUSED"
        severity = "CRIT"
        msg_tr = "Sistem DURDURULDU (Kill Switch)."
        msg_en = "System PAUSED (Kill Switch)."
        dedup_suffix = "KILL_SWITCH"

    elif etype == "STRATEGY_GAP_DETECTED":
        alert_type = "GAP"
        severity = "WARN"
        sid = evt.get("strategy_id", "UNKNOWN")
        delta = evt.get("payload", {}).get("delta", 0)
        msg_tr = f"Veri Boşluğu: {sid} ({delta}ms)"
        msg_en = f"Data Gap: {sid} ({delta}ms)"
        dedup_suffix = f"{sid}:{delta}"

    elif etype == "BROKER_MISCONFIG":
        alert_type = "BROKER"
        severity = "CRIT"
        sid = evt.get("strategy_id", "UNKNOWN")
        p = evt.get("payload", {})
        reason = p.get("reason", "UNKNOWN")
        msg_tr = f"Broker Hatası: {sid} - {reason}"
        msg_en = f"Broker Error: {sid} - {reason}"
        dedup_suffix = f"{sid}:{reason}"
        
    if alert_type:
        # Generate ID
        # ALERT_<TYPE>_<HASH(run_id, dedup_part)> ?
        # Or unique per occurrence? 
        # Requirement: "active içinde dedup_key varsa yeni alert üretme".
        # If we use a deterministic ID based on (run_id, type, dedup_suffix), idempotency is handled by FileNotifier.
        # But for streaming events like GAP, we might want one per occurrence or one per time window?
        # User spec says "Dedup key: <type>:<strategy_id>:<reason>".
        # Let's use that for deterministic ID generation.
        # But wait, we want to know WHEN it happened. If we re-emit the same ID with a new TS, FileNotifier overwrites/ignores.
        # If the alert is ACK'ed (moved to history), then a new occurrence will be created in active. This is desirable.
        # If it is NOT ACK'ed, it stays in active and we don't spam.
        
        raw_key = f"{run_id}:{alert_type}:{dedup_suffix}"
        h = hashlib.md5(raw_key.encode()).hexdigest()[:8]
        aid = f"ALERT_{alert_type}_{h}"
        
        return {
            "alert_id": aid,
            "type": alert_type,
            "severity": severity,
            "ts": ts,
            "source": {"cloud_run_id": run_id, "strategy_id": evt.get("strategy_id")},
            "message_tr": msg_tr,
            "message_en": msg_en,
            "event_ref": {"event_type": etype, "line": line_no},
            "dedup_key": raw_key
        }
        
    return None
