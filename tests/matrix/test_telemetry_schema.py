import pytest
from tezaver.matrix.core.telemetry import validate_event_dict, validate_ndjson_lines
import json

@pytest.mark.core
def test_telemetry_valid():
    """validate_event_dict returns True for valid events with required fields."""
    e = {
        "ts": 123, "event_type": "TEST", "run_id": "r1", 
        "trace": {}, "payload": {}
    }
    assert validate_event_dict(e) == True

def test_telemetry_missing_field():
    """validate_event_dict returns False when required fields are missing."""
    e = {"event_type": "TEST"}  # missing ts and run_id
    assert validate_event_dict(e) == False
    
def test_ndjson_lines():
    """validate_ndjson_lines returns True only when all lines are valid."""
    valid_line = {"ts": 1, "event_type": "A", "run_id": "r"}
    invalid_line = {"event_type": "B"}  # missing ts and run_id
    assert validate_ndjson_lines([valid_line]) == True
    assert validate_ndjson_lines([valid_line, invalid_line]) == False

