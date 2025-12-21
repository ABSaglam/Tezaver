import pytest
import json
from tezaver.matrix.core.candidate_v1 import ManifestV1, PayloadV1, generate_candidate_id, manifest_from_dict, payload_from_dict

def test_manifest_validation_success():
    valid_manifest = {
        "version": "1.1.2",
        "repo_version": "0.1.0",
        "bundle_id": "bundle_v1_12345",
        "symbol": "BTCUSDT",
        "tf": "15m",
        "export_time_utc": "2023-12-21T00:00:00Z",
        "metrics": {
            "trigger_resolve_rate": 1.0,
            "trigger_resolve_rate_by_source": {
                "join": 0.5, "join_1h_neighbor": 0.2, "derived_15m": 0.3, "fallback": 0.0, "unresolved": 0.0
            },
            "total_count": 10,
            "resolved_count": 10,
            "unresolved_count": 0,
            "unresolved_event_times": [],
            "join_coverage": 0.5
        },
        "fingerprints": {
            "data_fingerprint": "fp123",
            "config_signature": "sig456"
        },
        "status": "success"
    }
    manifest = manifest_from_dict(valid_manifest)
    assert manifest.symbol == "BTCUSDT"
    assert manifest.metrics.trigger_resolve_rate == 1.0
    
    # Test ID generation
    cid = generate_candidate_id(manifest)
    assert len(cid) == 16

def test_manifest_version_lock_fail():
    invalid_manifest = {
        "version": "1.2.0", # Unsupported version
        "repo_version": "0.1.0",
        "bundle_id": "bundle_v1_12345",
        "symbol": "BTCUSDT",
        "tf": "15m",
        "export_time_utc": "2023-12-21T00:00:00Z",
        "metrics": {
            "trigger_resolve_rate": 0.99,
            "trigger_resolve_rate_by_source": {"join": 0.99, "join_1h_neighbor": 0, "derived_15m": 0, "fallback": 0, "unresolved": 0},
            "total_count": 100, "resolved_count": 99, "unresolved_count": 1, "join_coverage": 0.99
        },
        "fingerprints": {"data_fingerprint": "fp", "config_signature": "sig"},
        "status": "success"
    }
    with pytest.raises(ValueError, match="Unsupported bundle version"):
        manifest_from_dict(invalid_manifest)

def test_payload_validation_success():
    # Minimal payload
    valid_payload = {
        "stories": [
            {
                "version": "1.1.2",
                "story_id": "S1",
                "symbol": "BTCUSDT",
                "context": {}, "entry": {}, "target": {}, "risk": {}, "family": {}, "quality": {}, "evidence": {}, "phases": []
            }
        ],
        "compiled_stories": {}
    }
    payload = payload_from_dict(valid_payload)
    assert len(payload.stories) == 1
    assert payload.stories[0].story_id == "S1"
