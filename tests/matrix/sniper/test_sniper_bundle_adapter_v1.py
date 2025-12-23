"""
Tests for Sniper Bundle Adapter v1
==================================

Test building SniperRunConfig from ApprovedRallyBundle v1 packages.
"""

import pytest
import tempfile
import json
from pathlib import Path

from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1, LoadedBundle
from tezaver.matrix.sniper.sniper_bundle_adapter_v1 import (
    build_sniper_run_config_from_bundle,
    SniperBundleRunConfig,
    emit_sniper_run_started,
    emit_sniper_run_finished,
    start_sniper_from_bundle
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
        bundle_id="test_bundle_001",
        symbol="BTCUSDT",
        timeframe="15m",
        event_id="event_123",
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
    bundle_dir: str = "/tmp/test_bundle",
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


class TestBuildSniperRunConfigFromBundle:
    """Test build_sniper_run_config_from_bundle function."""
    
    def test_build_config_pass(self):
        """Valid PASS bundle should build config correctly."""
        manifest = create_test_manifest(
            qc_verdict="PASS",
            qc_score=90,
            entry_ts="2025-01-01T01:00:00",
            exit_ts="2025-01-01T02:00:00",
            tier="GOLD"
        )
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        config = build_sniper_run_config_from_bundle(bundle)
        
        assert isinstance(config, SniperBundleRunConfig)
        assert config.symbol == "BTCUSDT"
        assert config.timeframe == "15m"
        assert config.bundle_id == "test_bundle_001"
        assert config.entry_ts == "2025-01-01T01:00:00"
        assert config.exit_ts == "2025-01-01T02:00:00"
        assert config.qc_score == 90
        assert config.tier == "GOLD"
        assert config.exit_missing is False
    
    def test_reject_qc_fail(self):
        """QC_FAIL bundle should raise ValueError."""
        manifest = create_test_manifest(qc_verdict="FAIL", qc_score=40)
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        with pytest.raises(ValueError) as exc_info:
            build_sniper_run_config_from_bundle(bundle)
        
        assert "BUNDLE_NOT_PASS" in str(exc_info.value)
    
    def test_reject_not_loaded_ok(self):
        """REJECTED bundle should raise ValueError."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="REJECTED", manifest=manifest, reject_reason="QC_FAIL")
        
        with pytest.raises(ValueError) as exc_info:
            build_sniper_run_config_from_bundle(bundle)
        
        assert "BUNDLE_NOT_LOADED_OK" in str(exc_info.value)
    
    def test_reject_discovered_status(self):
        """DISCOVERED status bundle should raise ValueError."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="DISCOVERED", manifest=manifest)
        
        with pytest.raises(ValueError) as exc_info:
            build_sniper_run_config_from_bundle(bundle)
        
        assert "BUNDLE_NOT_LOADED_OK" in str(exc_info.value)
    
    def test_missing_entry_reject(self):
        """Missing approved_entry_ts should raise ValueError."""
        manifest = create_test_manifest(entry_ts=None)
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        with pytest.raises(ValueError) as exc_info:
            build_sniper_run_config_from_bundle(bundle)
        
        assert "APPROVED_ENTRY_MISSING" in str(exc_info.value)
    
    def test_exit_missing_allowed(self):
        """Missing exit_ts should be allowed with exit_missing flag set."""
        manifest = create_test_manifest(exit_ts=None)
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        config = build_sniper_run_config_from_bundle(bundle)
        
        assert config.exit_ts is None
        assert config.exit_missing is True
    
    def test_config_to_dict(self):
        """Config should serialize to dict correctly."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        config = build_sniper_run_config_from_bundle(bundle)
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert config_dict["symbol"] == "BTCUSDT"
        assert config_dict["bundle_id"] == "test_bundle_001"


class TestTelemetryEmission:
    """Test telemetry event emission functions."""
    
    def test_sniper_run_started_contains_bundle_id(self, capsys):
        """SNIPER_RUN_STARTED should contain bundle_id."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        config = build_sniper_run_config_from_bundle(bundle)
        
        event = emit_sniper_run_started(config, "test_run_001")
        
        assert event["event_type"] == "SNIPER_RUN_STARTED"
        assert event["bundle_id"] == "test_bundle_001"
        assert event["run_id"] == "test_run_001"
        assert event["symbol"] == "BTCUSDT"
        assert event["qc_score"] == 85
        
        # Verify telemetry was printed
        captured = capsys.readouterr()
        assert "[TELEMETRY]" in captured.out
        assert "SNIPER_RUN_STARTED" in captured.out
    
    def test_sniper_run_finished_contains_bundle_id(self, capsys):
        """SNIPER_RUN_FINISHED should contain bundle_id."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        config = build_sniper_run_config_from_bundle(bundle)
        
        result_summary = {"cycles": 10, "pnl": 150.0}
        event = emit_sniper_run_finished(config, "test_run_001", result_summary)
        
        assert event["event_type"] == "SNIPER_RUN_FINISHED"
        assert event["bundle_id"] == "test_bundle_001"
        assert event["run_id"] == "test_run_001"
        assert event["result"]["cycles"] == 10
        assert event["result"]["pnl"] == 150.0


class TestStartSniperFromBundle:
    """Test high-level start_sniper_from_bundle function."""
    
    def test_start_valid_bundle(self):
        """Valid bundle should start successfully."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = start_sniper_from_bundle(bundle, run_id="custom_run_123")
        
        assert result["status"] == "STARTED"
        assert result["run_id"] == "custom_run_123"
        assert result["error"] is None
        assert result["config"]["bundle_id"] == "test_bundle_001"
        assert len(result["telemetry"]) == 1
        assert result["telemetry"][0]["event_type"] == "SNIPER_RUN_STARTED"
    
    def test_start_invalid_bundle_returns_error(self):
        """Invalid bundle should return error status."""
        manifest = create_test_manifest(qc_verdict="FAIL")
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = start_sniper_from_bundle(bundle)
        
        assert result["status"] == "ERROR"
        assert "BUNDLE_NOT_PASS" in result["error"]
        assert result["config"] is None
    
    def test_auto_generates_run_id(self):
        """Should auto-generate run_id if not provided."""
        manifest = create_test_manifest()
        bundle = create_test_bundle(status="LOADED_OK", manifest=manifest)
        
        result = start_sniper_from_bundle(bundle)
        
        assert result["run_id"].startswith("sniper_bundle_")
        assert len(result["run_id"]) > 20
