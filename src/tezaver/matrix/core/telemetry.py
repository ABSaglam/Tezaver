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
        "kind": final_type,  # MX-9340: Backward compat for tests reading e.get("kind")
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

def event_line(
    event_type: str,
    data: Dict[str, Any] = None,
    run_id: str = "unknown",
    config_signature: str = "unknown"
) -> str:
    """
    Creates a JSON-formatted telemetry line.
    Backward compatibility wrapper for normalize_event.
    """
    event = normalize_event(event_type, data, run_id, config_signature)
    return json.dumps(event)

def validate_event_dict(event: Dict[str, Any]) -> bool:
    """
    Validates that an event dict has required fields.
    """
    required = ["event_type", "ts", "run_id"]
    return all(k in event for k in required)

def validate_ndjson_lines(lines: list) -> bool:
    """
    Validates that all lines in an NDJSON list have required fields.
    """
    return all(validate_event_dict(line) for line in lines)
