"""
Tests for Reconcile Bundles v1
==============================

Test boot-time bundle reconciliation for Matrix.
"""

import pytest
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Any

from tezaver.matrix.bundles.bundle_registry import BundleRegistry
from tezaver.matrix.bundles.bundle_models_v1 import LoadedBundle, ApprovedRallyBundleManifestV1
from tezaver.matrix.bootstrap.reconcile_bundles_v1 import (
    reconcile_bundles_on_boot,
    get_global_registry,
    boot_reconcile_bundles
)


def create_minimal_bundle(
    root_dir: Path,
    symbol: str = "BTCUSDT",
    timeframe: str = "15m",
    event_id: str = "test_event_001",
    bundle_id: str = "test_bundle_001",
    qc_verdict: str = "PASS",
    qc_score: int = 85
) -> Path:
    """Create a minimal valid ApprovedRallyBundle v1 for testing."""
    bundle_dir = root_dir / symbol / timeframe / event_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        "bundle_version": "approved_rally_bundle_v1",
        "bundle_id": bundle_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "event_id": event_id,
        "event_time_iso": "2025-01-01T00:00:00",
        "approved": {
            "entry_bar_offset": 5,
            "entry_ts": "2025-01-01T01:00:00",
            "exit_bar_offset": 15,
            "exit_ts": "2025-01-01T03:00:00"
        },
        "qc": {
            "verdict": qc_verdict,
            "score": qc_score
        },
        "tier": "GOLD"
    }
    
    with open(bundle_dir / "manifest.json", 'w') as f:
        json.dump(manifest, f, indent=2)
    
    qc_report = {
        "event_id": event_id,
        "verdict": qc_verdict,
        "total_score": qc_score
    }
    
    with open(bundle_dir / "qc_report.json", 'w') as f:
        json.dump(qc_report, f, indent=2)
    
    return bundle_dir


class TestReconcileBundlesOnBoot:
    """Test reconcile_bundles_on_boot function."""
    
    def test_reconcile_with_pass_and_fail_bundles(self):
        """
        Test reconciliation with 1 PASS and 1 FAIL bundle.
        
        Should result in loaded_ok=1, rejected=1.
        """
        captured_events: List[Dict[str, Any]] = []
        
        def capture_emit(event):
            captured_events.append(event)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            # Create 1 PASS bundle
            create_minimal_bundle(
                root_dir=root,
                symbol="BTCUSDT",
                timeframe="15m",
                event_id="pass_event_001",
                bundle_id="pass_bundle_001",
                qc_verdict="PASS",
                qc_score=90
            )
            
            # Create 1 FAIL bundle
            create_minimal_bundle(
                root_dir=root,
                symbol="ETHUSDT",
                timeframe="1h",
                event_id="fail_event_001",
                bundle_id="fail_bundle_001",
                qc_verdict="FAIL",
                qc_score=40
            )
            
            # Create registry with "garbage" data
            registry = BundleRegistry()
            # Add some fake bundles to simulate pre-existing state
            fake_manifest = ApprovedRallyBundleManifestV1(
                bundle_version="v1",
                bundle_id="garbage_001",
                symbol="GARBAGE",
                timeframe="1m",
                event_id="garbage",
                event_time_iso="2020-01-01T00:00:00",
                approved_entry_bar_offset=1,
                approved_entry_ts="2020-01-01T00:00:00",
                qc_verdict="PASS",
                qc_score=50
            )
            registry.add(LoadedBundle(
                manifest=fake_manifest,
                bundle_dir="/tmp/garbage",
                status="LOADED_OK"
            ))
            
            # Verify garbage exists
            assert registry.counts()["total"] == 1
            
            # Reconcile
            result = reconcile_bundles_on_boot(
                root_path=str(root),
                registry=registry,
                emit=capture_emit
            )
            
            # Verify result
            assert result["status"] == "OK"
            assert result["counts"]["total"] == 2
            assert result["counts"]["loaded_ok"] == 1
            assert result["counts"]["rejected"] == 1
            assert result["duration_ms"] >= 0
            
            # Verify registry updated (garbage cleared)
            assert registry.counts()["total"] == 2
            assert registry.counts()["loaded_ok"] == 1
            assert registry.counts()["rejected"] == 1
            
            # Verify last_reconcile tracked
            assert registry.last_reconcile_ts is not None
            assert registry.last_reconcile_counts["loaded_ok"] == 1
            
            # Verify telemetry events
            assert len(captured_events) == 2
            
            start_event = captured_events[0]
            assert start_event["event_type"] == "BOOT_RECONCILE_STARTED"
            assert start_event["root_path"] == str(root)
            
            done_event = captured_events[1]
            assert done_event["event_type"] == "BOOT_RECONCILE_DONE"
            assert done_event["status"] == "OK"
            assert done_event["counts"]["loaded_ok"] == 1
            assert done_event["counts"]["rejected"] == 1
    
    def test_reconcile_empty_root(self):
        """Test reconciliation with empty/nonexistent root."""
        captured_events: List[Dict[str, Any]] = []
        
        def capture_emit(event):
            captured_events.append(event)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "nonexistent"
            
            registry = BundleRegistry()
            
            result = reconcile_bundles_on_boot(
                root_path=str(root),
                registry=registry,
                emit=capture_emit
            )
            
            # Should succeed with 0 counts
            assert result["status"] == "OK"
            assert result["counts"]["total"] == 0
            assert result["counts"]["loaded_ok"] == 0
            
            # Verify events
            assert len(captured_events) == 2
            assert captured_events[0]["event_type"] == "BOOT_RECONCILE_STARTED"
            assert captured_events[1]["event_type"] == "BOOT_RECONCILE_DONE"
    
    def test_reconcile_deterministic(self):
        """Test that multiple reconciliations produce same result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            # Create bundles
            create_minimal_bundle(
                root_dir=root,
                symbol="BTCUSDT",
                timeframe="15m",
                event_id="determ_001",
                bundle_id="determ_bundle_001",
                qc_verdict="PASS",
                qc_score=80
            )
            
            # First reconcile
            registry1 = BundleRegistry()
            result1 = reconcile_bundles_on_boot(str(root), registry1)
            
            # Second reconcile
            registry2 = BundleRegistry()
            result2 = reconcile_bundles_on_boot(str(root), registry2)
            
            # Same counts
            assert result1["counts"] == result2["counts"]
            assert registry1.counts() == registry2.counts()
    
    def test_reconcile_clears_previous_state(self):
        """Test that reconcile clears previous registry state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            # Create 1 bundle
            create_minimal_bundle(
                root_dir=root,
                symbol="BTCUSDT",
                timeframe="15m",
                event_id="clear_001",
                bundle_id="clear_bundle_001",
                qc_verdict="PASS",
                qc_score=85
            )
            
            # Registry with 5 fake bundles
            registry = BundleRegistry()
            for i in range(5):
                fake_manifest = ApprovedRallyBundleManifestV1(
                    bundle_version="v1",
                    bundle_id=f"fake_{i}",
                    symbol="FAKE",
                    timeframe="1m",
                    event_id=f"fake_{i}",
                    event_time_iso="2020-01-01T00:00:00",
                    approved_entry_bar_offset=1,
                    approved_entry_ts="2020-01-01T00:00:00",
                    qc_verdict="PASS",
                    qc_score=50
                )
                registry.add(LoadedBundle(
                    manifest=fake_manifest,
                    bundle_dir=f"/tmp/fake_{i}",
                    status="LOADED_OK"
                ))
            
            # Verify 5 fake bundles
            assert registry.counts()["total"] == 5
            
            # Reconcile
            result = reconcile_bundles_on_boot(str(root), registry)
            
            # Should have only 1 bundle (the real one)
            assert result["counts"]["total"] == 1
            assert registry.counts()["total"] == 1
    
    def test_reconcile_telemetry_printed(self, capsys):
        """Test that telemetry is printed when no emit callback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            registry = BundleRegistry()
            
            # Reconcile without emit callback
            result = reconcile_bundles_on_boot(str(root), registry)
            
            captured = capsys.readouterr()
            assert "BOOT_RECONCILE_STARTED" in captured.out
            assert "BOOT_RECONCILE_DONE" in captured.out


class TestGlobalRegistry:
    """Test global registry functions."""
    
    def test_get_global_registry_singleton(self):
        """Global registry should be singleton."""
        reg1 = get_global_registry()
        reg2 = get_global_registry()
        
        assert reg1 is reg2
    
    def test_boot_reconcile_uses_global_registry(self):
        """boot_reconcile_bundles should use global registry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = boot_reconcile_bundles(home_path=tmpdir)
            
            assert result["status"] == "OK"
