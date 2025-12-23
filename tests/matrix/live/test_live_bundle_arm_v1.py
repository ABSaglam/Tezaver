"""
Tests for LIVE Bundle Arm v1
=============================

Test LIVE arm from ApprovedRallyBundle v1 packages.
"""

import pytest
from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1, LoadedBundle
from tezaver.matrix.bundles.bundle_run_context_v1 import (
    BundleRunContextV1,
    build_context_from_loaded_bundle,
    emit_live_bundle_armed,
    arm_live_from_bundle
)


def create_test_manifest(
    qc_verdict: str = "PASS",
    qc_score: int = 88,
    entry_ts: str = "2025-01-01T01:00:00",
    exit_ts: str = None,
    tier: str = "SILVER"
) -> ApprovedRallyBundleManifestV1:
    """Create a test manifest with customizable fields."""
    return ApprovedRallyBundleManifestV1(
        bundle_version="approved_rally_bundle_v1",
        bundle_id="test_bundle_live_001",
        symbol="ETHUSDT",
        timeframe="1h",
        event_id="event_live_456",
        event_time_iso="2025-01-01T00:00:00",
        approved_entry_bar_offset=3,
        approved_entry_ts=entry_ts,
        qc_verdict=qc_verdict,
        qc_score=qc_score,
        approved_exit_bar_offset=8 if exit_ts else None,
        approved_exit_ts=exit_ts,
        tier=tier
    )


def create_test_bundle(
    status: str = "LOADED_OK",
    manifest: ApprovedRallyBundleManifestV1 = None,
    bundle_dir: str = "/tmp/test_live_bundle",
    reject_reason: str = None
) -> LoadedBundle:
    """Create a test LoadedBundle."""
    if manifest is None:
        manifest = create_test_manifest()
    
    return LoadedBundle(
        manifest=manifest,
        bundle_dir=bundle_dir,
        status=status,
        reject_reason=reject_reason
    )


class TestLiveBundleArmed:
    """Test LIVE bundle arm telemetry emission."""
    
    def test_live_bundle_armed_contains_bundle_id(self, capsys):
        """LIVE_BUNDLE_ARMED should contain bundle_id."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        ctx = build_context_from_loaded_bundle(bundle)
        
        event = emit_live_bundle_armed(ctx, "test_arm_001")
        
        assert event["event_type"] == "LIVE_BUNDLE_ARMED"
        assert event["bundle_id"] == "test_bundle_live_001"
        assert event["arm_id"] == "test_arm_001"
        assert event["symbol"] == "ETHUSDT"
        assert event["timeframe"] == "1h"
        assert event["qc_score"] == 88
        assert event["tier"] == "SILVER"
        
        # Verify telemetry was printed
        captured = capsys.readouterr()
        assert "[TELEMETRY]" in captured.out
        assert "LIVE_BUNDLE_ARMED" in captured.out
    
    def test_live_bundle_armed_includes_entry_exit(self, capsys):
        """LIVE_BUNDLE_ARMED should include entry/exit timestamps."""
        manifest = create_test_manifest(
            entry_ts="2025-01-01T01:00:00",
            exit_ts="2025-01-01T02:00:00"
        )
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        ctx = build_context_from_loaded_bundle(bundle)
        
        event = emit_live_bundle_armed(ctx, "test_arm_002")
        
        assert event["entry_ts"] == "2025-01-01T01:00:00"
        assert event["exit_ts"] == "2025-01-01T02:00:00"
        assert event["exit_missing"] is False


class TestArmLiveFromBundle:
    """Test high-level arm_live_from_bundle function."""
    
    def test_arm_valid_bundle(self):
        """Valid bundle should arm LIVE successfully."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = arm_live_from_bundle(bundle, arm_id="custom_arm_123")
        
        assert result["status"] == "ARMED"
        assert result["arm_id"] == "custom_arm_123"
        assert result["error"] is None
        assert result["context"]["bundle_id"] == "test_bundle_live_001"
        assert len(result["telemetry"]) == 1
        assert result["telemetry"][0]["event_type"] == "LIVE_BUNDLE_ARMED"
    
    def test_arm_invalid_bundle_returns_error(self):
        """Invalid bundle should return error status."""
        manifest = create_test_manifest(qc_verdict="FAIL")
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = arm_live_from_bundle(bundle)
        
        assert result["status"] == "ERROR"
        assert "BUNDLE_NOT_PASS" in result["error"]
        assert result["context"] is None
    
    def test_arm_rejected_bundle_returns_error(self):
        """REJECTED bundle should return error status."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="REJECTED", manifest=manifest, reject_reason="QC_FAIL")
        
        result = arm_live_from_bundle(bundle)
        
        assert result["status"] == "ERROR"
        assert "BUNDLE_NOT_LOADED_OK" in result["error"]
    
    def test_auto_generates_arm_id(self):
        """Should auto-generate arm_id if not provided."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = arm_live_from_bundle(bundle)
        
        assert result["arm_id"].startswith("live_arm_")
        assert len(result["arm_id"]) > 15
    
    def test_exit_missing_flag_set(self):
        """Should set exit_missing flag when exit_ts is None."""
        manifest = create_test_manifest(exit_ts=None)
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = arm_live_from_bundle(bundle)
        
        assert result["context"]["exit_missing"] is True
        assert result["telemetry"][0]["exit_missing"] is True
