from tezaver.matrix.core.audit import compute_audit_from_events
import json

def test_audit_no_trades():
    events = [
        json.dumps({"event_type": "CYCLE_STEP", "payload": {}}),
        json.dumps({"event_type": "RUN_END", "payload": {}})
    ]
    audit = compute_audit_from_events(events)
    assert audit["trades_count"] == 0

def test_audit_trades():
    events = [
        json.dumps({"event_type": "ORDER_FILLED", "payload": {}}),
        json.dumps({"event_type": "ORDER_FILLED", "payload": {}})
    ]
    audit = compute_audit_from_events(events)
    assert audit["trades_count"] == 2
