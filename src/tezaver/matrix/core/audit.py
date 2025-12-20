import json
from typing import List, Dict

def compute_audit_from_events(lines: List[str]) -> Dict:
    """Computes basic audit stats from event lines."""
    trades_count = 0
    run_id = "UNKNOWN"
    engine_version = "UNKNOWN"
    
    for line in lines:
        try:
            e = json.loads(line)
        except:
            continue
            
        # Capture run info from first valid event
        if run_id == "UNKNOWN":
            run_id = e.get("run_id", "UNKNOWN")
            trace = e.get("trace", {})
            engine_version = trace.get("engine_version", "UNKNOWN")
            
        etype = e.get("event_type")
        payload = e.get("payload", {})
        
        # Logic: If broker emits ORDER_FILLED or similar.
        # For now, we rely on core cycle writing events.
        # If we had "ORDER_FILLED", we count.
        if etype == "ORDER_FILLED":
            trades_count += 1
            
    return {
        "run_id": run_id,
        "engine_version": engine_version,
        "trades_count": trades_count,
        "gross_pnl": 0.0,
        "net_pnl": 0.0,
        "fees": 0.0
    }
