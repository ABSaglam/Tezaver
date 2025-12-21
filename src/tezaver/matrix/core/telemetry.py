import json
from datetime import datetime
from typing import Dict, Any, Optional
from tezaver.version import __version__, build_commit

def normalize_event(
    event_type: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    run_id: str = "unknown",
    config_signature: str = "unknown",
    data_fingerprint: str = ""
) -> Dict[str, Any]:
    """
    MX-5150: Standardizes telemetry event schema.
    Tr: Telemetry event şemasını standartlaştırır.
    """
    data = data or {}
    
    # Kind to event_type mapping (backward compatibility)
    final_type = event_type or data.get("event_type") or data.get("kind") or "UNKNOWN_EVENT"
    
    event = {
        "event_type": final_type,
        "ts": datetime.now().isoformat(),
        "run_id": run_id,
        "engine_version": f"v{__version__}",
        "build_commit": build_commit(),
        "config_signature": config_signature,
    }
    
    if data_fingerprint:
        event["data_fingerprint"] = data_fingerprint
        
    # Merge payload, avoiding overwriting mandatory fields
    for k, v in data.items():
        if k not in event:
            event[k] = v
            
    return event
