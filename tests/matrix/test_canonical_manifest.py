"""
PNL-1100: Canonical Manifest Normalization Tests
"""
import sys
import json
import tempfile
from pathlib import Path

sys.path.append("src")

from tezaver.matrix.core.candidate_v1 import manifest_from_dict, payload_from_dict


def test_nested_manifest_parse():
    """Golden/nested manifest (v1.1.x) should parse OK."""
    manifest = {
        "version": "1.1.2",
        "repo_version": "test",
        "bundle_id": "nested_test",
        "symbol": "BTCUSDT",
        "tf": "15m",
        "export_time_utc": "2023-12-01T00:00:00Z",
        "status": "OK",
        "metrics": {
            "trigger_resolve_rate": 0.95,
            "join_coverage": 0.80,
            "trigger_resolve_rate_by_source": {
                "join": 0.8,
                "join_1h_neighbor": 0.05,
                "derived_15m": 0.1,
                "fallback": 0.0,
                "unresolved": 0.05
            },
            "total_count": 10,
            "resolved_count": 9,
            "unresolved_count": 1,
            "unresolved_event_times": []
        },
        "fingerprints": {
            "data_fingerprint": "abc123",
            "config_signature": "xyz789"
        }
    }
    
    result = manifest_from_dict(manifest)
    assert result.symbol == "BTCUSDT"
    assert result.tf == "15m"
    assert result.metrics.trigger_resolve_rate == 0.95
    assert result.fingerprints.data_fingerprint == "abc123"
    print("SUCCESS: Nested manifest parsed OK")


def test_flat_manifest_parse():
    """Flat/legacy manifest (timeframe + flat fingerprints) should parse OK."""
    manifest = {
        "bundle_id": "flat_test",
        "symbol": "ETHUSDT",
        "timeframe": "1h",  # Not tf!
        "bundle_version": "1.1.0",  # Not version!
        "build_ts": "2023-11-01T00:00:00Z",
        "story_count": 5,
        "data_fingerprint": "flat_fp",  # Flat, not nested
        "config_signature": "flat_sig"
    }
    
    result = manifest_from_dict(manifest)
    assert result.symbol == "ETHUSDT"
    assert result.tf == "1h", f"Expected 1h, got {result.tf}"
    assert result.version == "1.1.0"
    assert result.fingerprints.data_fingerprint == "flat_fp"
    assert result.fingerprints.config_signature == "flat_sig"
    print("SUCCESS: Flat manifest parsed OK")


def test_registry_upsert():
    """CandidateRegistry.upsert should update existing or create new."""
    from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
    
    with tempfile.TemporaryDirectory() as tmpdir:
        reg_path = Path(tmpdir) / "test_reg.jsonl"
        registry = CandidateRegistry(registry_path=str(reg_path))
        
        # First upsert - should create
        # MX-9310: bundle_id is primary key for get/upsert
        registry.upsert(
            bundle_id="bundle1",
            symbol="BTCUSDT",
            tf="15m",
            bundle_path="/path/to/bundle",
            metrics={"trigger_resolve_rate": 0.9, "join_coverage": 0.8},
            candidate_id="test_cid"
        )
        
        # MX-9310: get() uses bundle_id as key
        cand = registry.get("bundle1")
        assert cand["status"] == "NEW"
        assert cand["resolve_rate"] == 0.9
        
        # Second upsert - should update (same bundle_id)
        registry.upsert(
            bundle_id="bundle1",
            symbol="BTCUSDT",
            tf="15m",
            bundle_path="/path/to/bundle_updated",
            metrics={"trigger_resolve_rate": 0.95, "join_coverage": 0.85},
            candidate_id="test_cid"
        )
        
        cand = registry.get("bundle1")
        assert cand["resolve_rate"] == 0.95
        assert cand["status"] == "NEW"  # Status preserved
        print("SUCCESS: Registry upsert works correctly")


def test_real_root_discovery():
    """Real root discovery and import should work."""
    from tezaver.matrix.apps.panel_health import run_health_check
    
    result = run_health_check()
    discovered = result.get("discovered_count", 0)
    imported = result.get("imported_count", 0)
    
    print(f"Real root: Discovered={discovered}, Imported={imported}")
    assert discovered >= 1, "Should discover at least 1 bundle"
    print(f"SUCCESS: Real root discovery works (discovered={discovered}, imported={imported})")


if __name__ == "__main__":
    print("=== PNL-1100: Canonical Manifest Normalization Tests ===")
    test_nested_manifest_parse()
    test_flat_manifest_parse()
    test_registry_upsert()
    test_real_root_discovery()
    print("\n=== All tests passed ===")
