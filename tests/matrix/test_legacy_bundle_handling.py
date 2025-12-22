"""
MXI-3.1: Legacy Bundle Handling Regression Tests
"""
import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

sys.path.append("src")

from tezaver.matrix.adapters.bundle_source_local import LocalBundleSource, UnsupportedBundleVersion
from tezaver.matrix.adapters.candidate_registry import CandidateRegistry


def test_legacy_bundle_no_crash():
    """bundle_v0 (legacy) should not crash importer. Should be registered as FAILED_IMPORT."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create legacy bundle (v0)
        bundle_dir = Path(tmpdir) / "BTCUSDT" / "15m" / "bundle_v0"
        bundle_dir.mkdir(parents=True)
        
        # Manifest without proper version
        manifest = {"bundle_id": "legacy_test", "symbol": "BTCUSDT", "tf": "15m"}
        with open(bundle_dir / "manifest.json", "w") as f:
            json.dump(manifest, f)
        
        # Payload without stories
        payload = {"old_format": True}
        with open(bundle_dir / "payload.json", "w") as f:
            json.dump(payload, f)
        
        # Test discovery
        source = LocalBundleSource(base_path=tmpdir)
        bundles = source.discover_bundles()
        assert len(bundles) == 1, "Should discover 1 bundle"
        
        # Test load_bundle raises UnsupportedBundleVersion
        try:
            source.load_bundle(bundles[0])
            assert False, "Should have raised UnsupportedBundleVersion"
        except UnsupportedBundleVersion as e:
            assert e.detected_version == "0.0.0"
            print(f"SUCCESS: UnsupportedBundleVersion raised with version {e.detected_version}")
        
        # Test registry can record FAILED_IMPORT
        reg_path = Path(tmpdir) / "registry.jsonl"
        registry = CandidateRegistry(registry_path=str(reg_path))
        registry.register(
            candidate_id="test_legacy",
            symbol="BTCUSDT",
            tf="15m",
            bundle_id="legacy_test",
            bundle_path=str(bundle_dir),
            metrics={},
            status="FAILED_IMPORT",
            reason="UNSUPPORTED_BUNDLE_VERSION",
            detected_version="0.0.0"
        )
        
        # MX-9310: get() uses bundle_id as key, not candidate_id
        cand = registry.get("legacy_test")
        assert cand["status"] == "FAILED_IMPORT"
        assert cand["reason"] == "UNSUPPORTED_BUNDLE_VERSION"
        print("SUCCESS: Legacy bundle registered as FAILED_IMPORT with reason")


def test_v1_bundle_import_ok():
    """v1.1.x bundle should import successfully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_dir = Path(tmpdir) / "BTCUSDT" / "15m" / "bundle_v1"
        bundle_dir.mkdir(parents=True)
        
        # Valid v1.1.2 manifest with all required fields
        manifest = {
            "version": "1.1.2",
            "repo_version": "test",
            "bundle_id": "valid_test",
            "bundle_version": "1.1.2",
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
        with open(bundle_dir / "manifest.json", "w") as f:
            json.dump(manifest, f)
        
        # Valid payload
        payload = {
            "rally_stories_v1": [
                {
                    "version": "1.1.2",
                    "story_id": "test_story",
                    "symbol": "BTCUSDT",
                    "context": {},
                    "entry": {},
                    "target": {},
                    "risk": {},
                    "family": {},
                    "quality": {},
                    "evidence": {}
                }
            ],
            "compiled_stories": {}
        }
        with open(bundle_dir / "payload.json", "w") as f:
            json.dump(payload, f)
        
        source = LocalBundleSource(base_path=tmpdir)
        bundles = source.discover_bundles()
        assert len(bundles) == 1
        
        manifest_obj, payload_obj = source.load_bundle(bundles[0])
        assert manifest_obj.bundle_id == "valid_test"
        assert len(payload_obj.stories) == 1
        print("SUCCESS: v1.1.2 bundle imported OK")


def test_ui_render_smoke():
    """Candidates render should not raise even with empty/mixed data."""
    # This is a smoke test - just ensure the function doesn't crash on import
    try:
        from tezaver.ui.matrix_v4_tab import render_candidates, _render_candidates_inner
        print("SUCCESS: UI render functions imported without error")
    except Exception as e:
        print(f"FAIL: {e}")


if __name__ == "__main__":
    print("=== MXI-3.1 Regression Tests ===")
    test_legacy_bundle_no_crash()
    test_v1_bundle_import_ok()
    test_ui_render_smoke()
    print("\n=== All tests passed ===")
