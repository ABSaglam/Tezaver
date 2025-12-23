"""
Tests for WAR Bundle Consume v1
================================

Test WAR run from ApprovedRallyBundle v1 packages.
"""

import pytest
from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1, LoadedBundle
from tezaver.matrix.bundles.bundle_run_context_v1 import (
    BundleRunContextV1,
    build_context_from_loaded_bundle,
    emit_war_run_started,
    emit_war_run_finished,
    start_war_from_bundle
)


def create_test_manifest(
    qc_verdict: str = "PASS",
    qc_score: int = 85,
    entry_ts: str = "2025-01-01T01:00:00",
    exit_ts: str = None,
    tier: str = "GOLD"
) -> ApprovedRallyBundleManifestV1:
    """Create a test manifest with customizable fields."""
    return ApprovedRallyBundleManifestV1(
        bundle_version="approved_rally_bundle_v1",
        bundle_id="test_bundle_war_001",
        symbol="BTCUSDT",
        timeframe="15m",
        event_id="event_war_123",
        event_time_iso="2025-01-01T00:00:00",
        approved_entry_bar_offset=5,
        approved_entry_ts=entry_ts,
        qc_verdict=qc_verdict,
        qc_score=qc_score,
        approved_exit_bar_offset=10 if exit_ts else None,
        approved_exit_ts=exit_ts,
        tier=tier
    )


def create_test_bundle(
    status: str = "LOADED_OK",
    manifest: ApprovedRallyBundleManifestV1 = None,
    bundle_dir: str = "/tmp/test_war_bundle",
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


class TestBuildContextFromLoadedBundle:
    """Test build_context_from_loaded_bundle function."""
    
    def test_build_context_pass(self):
        """Valid PASS bundle should build context correctly."""
        manifest = create_test_manifest(
            qc_verdict="PASS",
            qc_score=90,
            entry_ts="2025-01-01T01:00:00",
            exit_ts="2025-01-01T02:00:00",
            tier="GOLD"
        )
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        ctx = build_context_from_loaded_bundle(bundle)
        
        assert isinstance(ctx, BundleRunContextV1)
        assert ctx.symbol == "BTCUSDT"
        assert ctx.timeframe == "15m"
        assert ctx.bundle_id == "test_bundle_war_001"
        assert ctx.entry_ts == "2025-01-01T01:00:00"
        assert ctx.exit_ts == "2025-01-01T02:00:00"
        assert ctx.qc_score == 90
        assert ctx.tier == "GOLD"
        assert ctx.exit_missing is False
        assert ctx.event_id == "event_war_123"
    
    def test_reject_qc_fail(self):
        """QC_FAIL bundle should raise ValueError."""
        manifest = create_test_manifest(qc_verdict="FAIL", qc_score=40)
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        with pytest.raises(ValueError) as exc_info:
            build_context_from_loaded_bundle(bundle)
        
        assert "BUNDLE_NOT_PASS" in str(exc_info.value)
    
    def test_reject_not_loaded_ok(self):
        """REJECTED bundle should raise ValueError."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="REJECTED", manifest=manifest, reject_reason="QC_FAIL")
        
        with pytest.raises(ValueError) as exc_info:
            build_context_from_loaded_bundle(bundle)
        
        assert "BUNDLE_NOT_LOADED_OK" in str(exc_info.value)
    
    def test_context_to_dict(self):
        """Context should serialize to dict correctly."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        ctx = build_context_from_loaded_bundle(bundle)
        ctx_dict = ctx.to_dict()
        
        assert isinstance(ctx_dict, dict)
        assert ctx_dict["symbol"] == "BTCUSDT"
        assert ctx_dict["bundle_id"] == "test_bundle_war_001"


class TestWarTelemetryEmission:
    """Test WAR telemetry event emission functions."""
    
    def test_war_run_started_contains_bundle_id(self, capsys):
        """WAR_RUN_STARTED should contain bundle_id."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        ctx = build_context_from_loaded_bundle(bundle)
        
        event = emit_war_run_started(ctx, "test_war_run_001")
        
        assert event["event_type"] == "WAR_RUN_STARTED"
        assert event["bundle_id"] == "test_bundle_war_001"
        assert event["run_id"] == "test_war_run_001"
        assert event["symbol"] == "BTCUSDT"
        assert event["qc_score"] == 85
        
        # Verify telemetry was printed
        captured = capsys.readouterr()
        assert "[TELEMETRY]" in captured.out
        assert "WAR_RUN_STARTED" in captured.out
    
    def test_war_run_finished_contains_bundle_id(self, capsys):
        """WAR_RUN_FINISHED should contain bundle_id."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        ctx = build_context_from_loaded_bundle(bundle)
        
        result_summary = {"coins_tested": 5, "total_pnl": 250.0}
        event = emit_war_run_finished(ctx, "test_war_run_001", result_summary)
        
        assert event["event_type"] == "WAR_RUN_FINISHED"
        assert event["bundle_id"] == "test_bundle_war_001"
        assert event["run_id"] == "test_war_run_001"
        assert event["result"]["coins_tested"] == 5
        assert event["result"]["total_pnl"] == 250.0


class TestStartWarFromBundle:
    """Test high-level start_war_from_bundle function."""
    
    def test_start_valid_bundle(self):
        """Valid bundle should start WAR successfully."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = start_war_from_bundle(bundle, run_id="custom_war_run_123")
        
        assert result["status"] == "STARTED"
        assert result["run_id"] == "custom_war_run_123"
        assert result["error"] is None
        assert result["context"]["bundle_id"] == "test_bundle_war_001"
        assert len(result["telemetry"]) == 1
        assert result["telemetry"][0]["event_type"] == "WAR_RUN_STARTED"
    
    def test_start_invalid_bundle_returns_error(self):
        """Invalid bundle should return error status."""
        manifest = create_test_manifest(qc_verdict="FAIL")
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = start_war_from_bundle(bundle)
        
        assert result["status"] == "ERROR"
        assert "BUNDLE_NOT_PASS" in result["error"]
        assert result["context"] is None
    
    def test_auto_generates_run_id(self):
        """Should auto-generate run_id if not provided."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = start_war_from_bundle(bundle)
        
        assert result["run_id"].startswith("war_bundle_")
        assert len(result["run_id"]) > 15
