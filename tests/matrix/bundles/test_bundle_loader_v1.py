"""
Tests for Bundle Loader v1
===========================

Test bundle scanning, loading, and QC enforcement.
"""

import pytest
import tempfile
import json
from pathlib import Path

from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1
from tezaver.matrix.bundles.bundle_loader_v1 import scan_bundles, load_manifest, load_bundle, load_all_bundles
from tezaver.matrix.bundles.bundle_registry import BundleRegistry


class TestBundleLoaderV1:
    """Test bundle loader functionality."""
    
    def test_scan_discovers_manifests(self):
        """Scan should discover bundle directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 2 bundles
            for i in range(2):
                bundle_dir = Path(tmpdir) / "BTCUSDT" / "15m" / f"event_{i}"
                bundle_dir.mkdir(parents=True)
                
                manifest = {
                    "bundle_version": "approved_rally_bundle_v1",
                    "bundle_id": f"test_{i}",
                    "symbol": "BTCUSDT",
                    "timeframe": "15m",
                    "event_id": f"event_{i}",
                    "event_time_iso": "2025-01-01T00:00:00",
                    "approved": {
                        "entry_bar_offset": 5,
                        "entry_ts": "2025-01-01T01:00:00"
                    },
                    "qc": {
                        "verdict": "PASS",
                        "score": 80
                    }
                }
                
                with open(bundle_dir / "manifest.json", 'w') as f:
                    json.dump(manifest, f)
            
            # Scan
            bundle_dirs = scan_bundles(tmpdir)
            
            assert len(bundle_dirs) == 2
    
    def test_load_pass_bundle_ok(self):
        """PASS bundle should load successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "BTCUSDT" / "15m" / "test_event"
            bundle_dir.mkdir(parents=True)
            
            manifest = {
                "bundle_version": "approved_rally_bundle_v1",
                "bundle_id": "test_bundle",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "event_id": "test_event",
                "event_time_iso": "2025-01-01T00:00:00",
                "approved": {
                    "entry_bar_offset": 5,
                    "entry_ts": "2025-01-01T01:00:00"
                },
                "qc": {
                    "verdict": "PASS",
                    "score": 85
                }
            }
            
            with open(bundle_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f)
            
            # Load
            loaded = load_bundle(bundle_dir, emit_telemetry=False)
            
            assert loaded.status == "LOADED_OK"
            assert loaded.reject_reason is None
            assert loaded.manifest.qc_verdict == "PASS"
            assert loaded.manifest.qc_score == 85
    
    def test_load_fail_bundle_rejected(self):
        """FAIL bundle should be rejected with reason QC_FAIL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "ETHUSDT" / "1h" / "test_event"
            bundle_dir.mkdir(parents=True)
            
            manifest = {
                "bundle_version": "approved_rally_bundle_v1",
                "bundle_id": "test_bundle_fail",
                "symbol": "ETHUSDT",
                "timeframe": "1h",
                "event_id": "test_event",
                "event_time_iso": "2025-01-01T00:00:00",
                "approved": {
                    "entry_bar_offset": 5,
                    "entry_ts": "2025-01-01T01:00:00"
                },
                "qc": {
                    "verdict": "FAIL",
                    "score": 40
                }
            }
            
            with open(bundle_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f)
            
            # Load
            loaded = load_bundle(bundle_dir, emit_telemetry=False)
            
            assert loaded.status == "REJECTED"
            assert loaded.reject_reason == "QC_FAIL"
            assert loaded.manifest.qc_verdict == "FAIL"
    
    def test_invalid_manifest_rejected(self):
        """Invalid manifest should be rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bundle_dir = Path(tmpdir) / "SOLUSDT" / "4h" / "test_event"
            bundle_dir.mkdir(parents=True)
            
            # Missing required field (event_id)
            manifest = {
                "bundle_version": "approved_rally_bundle_v1",
                "bundle_id": "test_invalid",
                "symbol": "SOLUSDT",
                "timeframe": "4h"
                # Missing event_id, event_time_iso, approved, qc
            }
            
            with open(bundle_dir / "manifest.json", 'w') as f:
                json.dump(manifest, f)
            
            # Load
            loaded = load_bundle(bundle_dir, emit_telemetry=False)
            
            assert loaded.status == "REJECTED"
            assert "MANIFEST_INVALID" in loaded.reject_reason
    
    def test_registry_counts(self):
        """Registry should track counts correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            registry = BundleRegistry()
            
            # Create 2 PASS bundles and 1 FAIL bundle
            for i in range(3):
                bundle_dir = Path(tmpdir) / "BTCUSDT" / "15m" / f"event_{i}"
                bundle_dir.mkdir(parents=True)
                
                verdict = "PASS" if i < 2 else "FAIL"
                score = 80 if i < 2 else 40
                
                manifest = {
                    "bundle_version": "approved_rally_bundle_v1",
                    "bundle_id": f"test_{i}",
                    "symbol": "BTCUSDT",
                    "timeframe": "15m",
                    "event_id": f"event_{i}",
                    "event_time_iso": "2025-01-01T00:00:00",
                    "approved": {
                        "entry_bar_offset": 5,
                        "entry_ts": "2025-01-01T01:00:00"
                    },
                    "qc": {
                        "verdict": verdict,
                        "score": score
                    }
                }
                
                with open(bundle_dir / "manifest.json", 'w') as f:
                    json.dump(manifest, f)
            
            # Load all
            load_all_bundles(tmpdir, registry=registry)
            
            # Check counts
            counts = registry.counts()
            
            assert counts["loaded_ok"] == 2  # 2 PASS bundles
            assert counts["rejected"] == 1   # 1 FAIL bundle
            assert counts["total"] == 3
