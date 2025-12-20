from tezaver.matrix.core.telemetry import validate_event_dict, validate_ndjson_lines
import json

def test_telemetry_valid():
    e = {
        "ts": 123, "event_type": "TEST", "run_id": "r1", 
        "trace": {}, "payload": {}
    }
    assert not validate_event_dict(e)

def test_telemetry_missing_field():
    e = {"event_type": "TEST"}
    errs = validate_event_dict(e)
    assert any("ts" in x for x in errs)
    
def test_ndjson_lines():
    lines = [
        json.dumps({"ts":1, "event_type":"A", "run_id":"r", "trace":{}, "payload":{}}),
        "invalid json"
    ]
    errs = validate_ndjson_lines(lines)
    assert len(errs) == 1
    assert "Invalid JSON" in errs[0]
