import pytest
from tezaver.matrix.core.telemetry import normalize_event

def test_telemetry_schema_standardization():
    # Test normalization with explicit event_type
    res = normalize_event(
        event_type="TEST_EVENT",
        data={"meta": "val"},
        run_id="run_123",
        config_signature="sig_abc"
    )
    
    assert res["event_type"] == "TEST_EVENT"
    assert res["run_id"] == "run_123"
    assert res["config_signature"] == "sig_abc"
    assert "ts" in res
    assert "engine_version" in res
    assert "build_commit" in res
    assert res["meta"] == "val"

def test_telemetry_kind_mapping():
    # Test falling back from kind to event_type
    res = normalize_event(
        data={"kind": "LEGACY_KIND", "other": 1},
        run_id="r",
        config_signature="s"
    )
    
    assert res["event_type"] == "LEGACY_KIND"
    assert "kind" in res
    assert res["other"] == 1

def test_telemetry_data_fingerprint():
    # Test optional field
    res = normalize_event(
        event_type="FOO",
        run_id="r",
        config_signature="s",
        data_fingerprint="fp_999"
    )
    assert res["data_fingerprint"] == "fp_999"

def test_mandatory_field_protection():
    # Verify that payload doesn't overwrite system fields
    res = normalize_event(
        event_type="PROTECTED",
        data={"ts": "fake_time", "run_id": "fake_id"},
        run_id="real_id",
        config_signature="real_sig"
    )
    
    assert res["run_id"] == "real_id"
    assert res["ts"] != "fake_time"
