from tezaver.matrix.ports.candidate_bundle import validate_bundle_dict, CandidateBundle

def test_valid_bundle_schema():
    d = {
        "symbol": "BTC",
        "timeframe": "15m",
        "bundle_version": "v1",
        "build_ts": "2025-12-20T10:00:00",
        "story": {
            "phases": [{"name": "P1", "start_bar": 100, "end_bar": 200}],
            "anchors": {"entry_bar": 150, "invalidation_bar": 90}
        }
    }
    errors = validate_bundle_dict(d)
    assert not errors

def test_missing_field():
    d = {"symbol": "BTC"}
    errors = validate_bundle_dict(d)
    assert any("Missing required field: timeframe" in e for e in errors)

def test_invalid_phase_range():
    d = {
        "symbol": "BTC",
        "timeframe": "15m",
        "bundle_version": "v1",
        "build_ts": "NOW",
        "story": {
            "phases": [{"name": "P1", "start_bar": 200, "end_bar": 100}], # Invalid
            "anchors": {"entry_bar": 150, "invalidation_bar": 90}
        }
    }
    errors = validate_bundle_dict(d)
    assert any("start_bar (200) > end_bar (100)" in e for e in errors)
