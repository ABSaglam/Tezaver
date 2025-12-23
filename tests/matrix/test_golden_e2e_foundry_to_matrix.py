"""
Golden E2E Test: Foundry → Matrix → Sniper/WAR/LIVE
=====================================================

End-to-end test validating bundle_id trace from bundle creation
through Matrix load to Sniper/WAR/LIVE execution.

This test validates:
1. Bundle created with QC PASS + manifest
2. Matrix loads bundle as LOADED_OK
3. Sniper start emits SNIPER_RUN_STARTED with bundle_id
4. WAR start emits WAR_RUN_STARTED with bundle_id
5. LIVE arm emits LIVE_BUNDLE_ARMED with bundle_id
6. All events have consistent bundle_id
"""

import pytest
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Any

from tezaver.matrix.bundles.bundle_loader_v1 import load_all_bundles, load_bundle
from tezaver.matrix.bundles.bundle_registry import BundleRegistry
from tezaver.matrix.bundles.bundle_run_context_v1 import (
    build_context_from_loaded_bundle,
    start_war_from_bundle,
    arm_live_from_bundle
)
from tezaver.matrix.sniper.sniper_bundle_adapter_v1 import start_sniper_from_bundle


# =============================================================================
# Test Fixtures
# =============================================================================

def create_minimal_bundle(
    root_dir: Path,
    symbol: str = "BTCUSDT",
    timeframe: str = "15m",
    event_id: str = "golden_e2e_event_001",
    bundle_id: str = "golden_e2e_bundle_001",
    qc_verdict: str = "PASS",
    qc_score: int = 85
) -> Path:
    """
    Create a minimal valid ApprovedRallyBundle v1 for E2E testing.
    
    Creates:
    - manifest.json with all required fields
    - qc_report.json with PASS verdict
    - (optional) price_window.parquet placeholder
    
    Returns:
        Path to created bundle directory
    """
    # Create bundle directory structure: {root}/approved_bundles_v1/{symbol}/{tf}/{event_id}
    bundle_dir = root_dir / "approved_bundles_v1" / symbol / timeframe / event_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    
    # Create manifest.json
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
        "tier": "GOLD",
        "pointers": {
            "annotation_source": "ony_events_v1"
        },
        "trace": {
            "created_by": "golden_e2e_test"
        }
    }
    
    with open(bundle_dir / "manifest.json", 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Create qc_report.json
    qc_report = {
        "event_id": event_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "total_score": qc_score,
        "verdict": qc_verdict,
        "rules_applied": 7,
        "rules_passed": 7 if qc_verdict == "PASS" else 3,
        "created_at": "2025-01-01T00:30:00"
    }
    
    with open(bundle_dir / "qc_report.json", 'w') as f:
        json.dump(qc_report, f, indent=2)
    
    return bundle_dir


# =============================================================================
# Golden E2E Test
# =============================================================================

@pytest.mark.golden_e2e
class TestGoldenE2EFoundryToMatrix:
    """
    Golden E2E test validating bundle_id trace from Foundry to Matrix.
    
    Steps:
    1. Create minimal bundle (simulates Foundry output)
    2. Load bundle via Matrix loader
    3. Run Sniper from bundle
    4. Run WAR from bundle
    5. Arm LIVE from bundle
    6. Verify all telemetry events have same bundle_id
    """
    
    def test_golden_e2e_foundry_to_matrix_bundle_trace(self, capsys):
        """
        Full E2E test: Foundry → Matrix → Sniper/WAR/LIVE with bundle_id trace.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            # =================================================================
            # Step 1: Create Bundle (Foundry simulation)
            # =================================================================
            bundle_id = "golden_e2e_BTCUSDT_15m_001"
            bundle_dir = create_minimal_bundle(
                root_dir=root,
                symbol="BTCUSDT",
                timeframe="15m",
                event_id="rally_golden_001",
                bundle_id=bundle_id,
                qc_verdict="PASS",
                qc_score=88
            )
            
            assert bundle_dir.exists()
            assert (bundle_dir / "manifest.json").exists()
            assert (bundle_dir / "qc_report.json").exists()
            
            # =================================================================
            # Step 2: Load Bundle via Matrix Loader
            # =================================================================
            registry = BundleRegistry()
            bundles_root = root / "approved_bundles_v1"
            loaded_bundles = load_all_bundles(
                root_path=str(bundles_root),
                registry=registry
            )
            
            # Verify registry counts
            counts = registry.counts()
            assert counts["loaded_ok"] == 1, f"Expected 1 LOADED_OK, got {counts}"
            assert counts["rejected"] == 0, f"Unexpected rejects: {counts}"
            
            # Get the LOADED_OK bundle
            loaded_list = registry.list(status="LOADED_OK")
            assert len(loaded_list) == 1
            loaded_bundle = loaded_list[0]
            assert loaded_bundle.manifest.bundle_id == bundle_id
            
            # Capture telemetry from load (printed to stdout)
            load_output = capsys.readouterr()
            assert "BUNDLE_LOADED" in load_output.out
            assert bundle_id in load_output.out
            
            # =================================================================
            # Step 3: Run Sniper from Bundle
            # =================================================================
            sniper_result = start_sniper_from_bundle(
                bundle=loaded_bundle,
                run_id="sniper_golden_run_001"
            )
            
            assert sniper_result["status"] == "STARTED"
            assert sniper_result["config"]["bundle_id"] == bundle_id
            assert len(sniper_result["telemetry"]) >= 1
            
            sniper_event = sniper_result["telemetry"][0]
            assert sniper_event["event_type"] == "SNIPER_RUN_STARTED"
            assert sniper_event["bundle_id"] == bundle_id
            
            # Capture sniper telemetry output
            sniper_output = capsys.readouterr()
            assert "SNIPER_RUN_STARTED" in sniper_output.out
            
            # =================================================================
            # Step 4: Run WAR from Bundle
            # =================================================================
            war_result = start_war_from_bundle(
                bundle=loaded_bundle,
                run_id="war_golden_run_001"
            )
            
            assert war_result["status"] == "STARTED"
            assert war_result["context"]["bundle_id"] == bundle_id
            assert len(war_result["telemetry"]) >= 1
            
            war_event = war_result["telemetry"][0]
            assert war_event["event_type"] == "WAR_RUN_STARTED"
            assert war_event["bundle_id"] == bundle_id
            
            # Capture WAR telemetry output
            war_output = capsys.readouterr()
            assert "WAR_RUN_STARTED" in war_output.out
            
            # =================================================================
            # Step 5: Arm LIVE from Bundle
            # =================================================================
            live_result = arm_live_from_bundle(
                bundle=loaded_bundle,
                arm_id="live_golden_arm_001"
            )
            
            assert live_result["status"] == "ARMED"
            assert live_result["context"]["bundle_id"] == bundle_id
            assert len(live_result["telemetry"]) >= 1
            
            live_event = live_result["telemetry"][0]
            assert live_event["event_type"] == "LIVE_BUNDLE_ARMED"
            assert live_event["bundle_id"] == bundle_id
            
            # Capture LIVE telemetry output
            live_output = capsys.readouterr()
            assert "LIVE_BUNDLE_ARMED" in live_output.out
            
            # =================================================================
            # Step 6: Verify Consistent bundle_id Across All Events
            # =================================================================
            all_events = [
                ("SNIPER_RUN_STARTED", sniper_event),
                ("WAR_RUN_STARTED", war_event),
                ("LIVE_BUNDLE_ARMED", live_event),
            ]
            
            for event_type, event in all_events:
                assert event["bundle_id"] == bundle_id, \
                    f"{event_type} has wrong bundle_id: {event['bundle_id']} != {bundle_id}"
            
            # Verify common fields present
            for event_type, event in all_events:
                assert "ts" in event, f"{event_type} missing ts"
                assert "symbol" in event, f"{event_type} missing symbol"
                assert "timeframe" in event, f"{event_type} missing timeframe"
                assert event["symbol"] == "BTCUSDT"
                assert event["timeframe"] == "15m"
    
    def test_golden_e2e_qc_fail_rejected(self):
        """
        E2E test: QC FAIL bundle is rejected, cannot be used for Sniper/WAR/LIVE.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            # Create FAIL bundle
            bundle_dir = create_minimal_bundle(
                root_dir=root,
                symbol="ETHUSDT",
                timeframe="1h",
                event_id="rally_fail_001",
                bundle_id="fail_bundle_001",
                qc_verdict="FAIL",
                qc_score=45
            )
            
            # Load via Matrix
            registry = BundleRegistry()
            bundles_root = root / "approved_bundles_v1"
            load_all_bundles(
                root_path=str(bundles_root),
                registry=registry
            )
            
            # Verify rejected
            counts = registry.counts()
            assert counts["loaded_ok"] == 0
            assert counts["rejected"] == 1
            
            # Get rejected bundle
            rejected_list = registry.list(status="REJECTED")
            assert len(rejected_list) == 1
            rejected_bundle = rejected_list[0]
            assert rejected_bundle.reject_reason == "QC_FAIL"
            
            # Attempt to use for Sniper - should error
            sniper_result = start_sniper_from_bundle(bundle=rejected_bundle)
            assert sniper_result["status"] == "ERROR"
            assert "BUNDLE_NOT_LOADED_OK" in sniper_result["error"]
            
            # Attempt to use for WAR - should error
            war_result = start_war_from_bundle(bundle=rejected_bundle)
            assert war_result["status"] == "ERROR"
            assert "BUNDLE_NOT_LOADED_OK" in war_result["error"]
            
            # Attempt to use for LIVE - should error
            live_result = arm_live_from_bundle(bundle=rejected_bundle)
            assert live_result["status"] == "ERROR"
            assert "BUNDLE_NOT_LOADED_OK" in live_result["error"]
    
    def test_golden_e2e_bundle_context_fields(self):
        """
        E2E test: Verify BundleRunContextV1 captures all expected fields.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            
            bundle_id = "context_test_bundle_001"
            bundle_dir = create_minimal_bundle(
                root_dir=root,
                symbol="SOLUSDT",
                timeframe="4h",
                event_id="rally_context_001",
                bundle_id=bundle_id,
                qc_verdict="PASS",
                qc_score=92
            )
            
            # Load bundle
            loaded_bundle = load_bundle(bundle_dir, emit_telemetry=False)
            assert loaded_bundle.status == "LOADED_OK"
            
            # Build context
            ctx = build_context_from_loaded_bundle(loaded_bundle)
            
            # Verify all fields
            assert ctx.bundle_id == bundle_id
            assert ctx.symbol == "SOLUSDT"
            assert ctx.timeframe == "4h"
            assert ctx.qc_score == 92
            assert ctx.tier == "GOLD"
            assert ctx.entry_ts == "2025-01-01T01:00:00"
            assert ctx.exit_ts == "2025-01-01T03:00:00"
            assert ctx.exit_missing is False
            assert ctx.event_id == "rally_context_001"
            assert ctx.trace == {"created_by": "golden_e2e_test"}
            
            # Verify to_dict
            ctx_dict = ctx.to_dict()
            assert ctx_dict["bundle_id"] == bundle_id
            assert "manifest_path" in ctx_dict
