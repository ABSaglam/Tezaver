import json
from typing import List, Dict

REQUIRED_FIELDS = ["ts", "event_type", "run_id", "trace", "payload"]

def event_line(e: Dict) -> str:
    """Returns a deterministic JSON line for an event."""
    return json.dumps(e, sort_keys=True)

def validate_event_dict(e: Dict) -> List[str]:
    """Validates a single event dictionary against mandatory schema."""
    errors = []
    for field in REQUIRED_FIELDS:
        if field not in e:
            errors.append(f"Missing required field: {field}")
            
    # Trace validation
    if "trace" in e:
        trace = e["trace"]
        if not isinstance(trace, dict):
             errors.append("Field 'trace' must be a dict")
             
    return errors

def validate_ndjson_lines(lines: List[str]) -> List[str]:
    """Validates a list of NDJSON event lines."""
    all_errors = []
    for idx, line in enumerate(lines):
        try:
            e = json.loads(line)
            errs = validate_event_dict(e)
            for err in errs:
                all_errors.append(f"Line {idx+1}: {err}")
        except json.JSONDecodeError:
            all_errors.append(f"Line {idx+1}: Invalid JSON")
            
    return all_errors
