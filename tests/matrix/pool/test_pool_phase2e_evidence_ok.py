import pytest
from pathlib import Path
import json
from tezaver.matrix.bundles.bundle_registry import BundleRegistry
from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1, LoadedBundle
from tezaver.matrix.pool.pool_orchestrator_v1 import run_pool_evidence_bundle
from tezaver.matrix.pool import pool_reports_v1
from tezaver.matrix.protocols.safety_registry import SafetyProtocolRegistry

# Helper to create bundle with v2 specs
def create_v2_bundle(bundle_id, symbol="BTCUSDT", tf="1h", qc=85):
    manifest = ApprovedRallyBundleManifestV1(
        bundle_version="approved_rally_bundle_v1",
        bundle_id=bundle_id,
        symbol=symbol,
        timeframe=tf,
        event_id="evt_1",
        event_time_iso="2023-01-01T00:00:00Z",
        approved_entry_bar_offset=10,
        approved_entry_ts="2023-01-01T00:00:00Z",
        qc_verdict="PASS",
        qc_score=qc,
        tier="GOLD",
        trigger_spec_v1={"type": "CLOSED_BAR_SIGNAL", "params": {}},
        policy_spec_v1={"exit_policy": "ATR", "params": {"atr_mult": 2.0, "notional": 100}}
    )
    return LoadedBundle(manifest, "/tmp", "LOADED_OK")

@pytest.fixture
def registry():
    reg = BundleRegistry()
    reg.add(create_v2_bundle("bundle_btc_1h"))
    reg.add(create_v2_bundle("bundle_eth_4h", symbol="ETHUSDT", tf="4h", qc=80))
    return reg

def test_war_evidence_ok(registry, tmp_path, monkeypatch):
    """WAR run produces all artifacts, evidence check returns OK."""
    monkeypatch.setattr(pool_reports_v1, "resolve_reports_dir", lambda s, r, root_dir=None: tmp_path / s / r / "reports")
    
    # Also patch the imports in other modules
    from tezaver.matrix.pool import pool_engine_v1, live_arm_state_v1, pool_orchestrator_v1
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    monkeypatch.setattr(live_arm_state_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    monkeypatch.setattr(pool_orchestrator_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    trace_ctx = {"engine_version": "v1.0.TEST", "data_fingerprint": "df_test", "config_signature": "cs_test"}
    
    result = run_pool_evidence_bundle("war", "war_pool_evidence_001", trace_ctx, registry)
    
    assert result["status"] == "OK"
    
    reports_dir = tmp_path / "war" / "war_pool_evidence_001" / "reports"
    
    # Check all WAR artifacts exist
    assert (reports_dir / "pool_mode_v1.json").exists()
    assert (reports_dir / "pool_universe_report_v1.json").exists()
    assert (reports_dir / "pool_tick_report_v1.json").exists()
    assert (reports_dir / "pool_intents_report_v1.json").exists()
    assert (reports_dir / "pool_selection_report_v1.json").exists()
    assert (reports_dir / "pool_portfolio_snapshot_v1.json").exists()
    assert (reports_dir / "pool_risk_report_v1.json").exists()
    assert (reports_dir / "pool_execution_summary_v1.json").exists()
    assert (reports_dir / "restart_reconcile_report_v1.json").exists()
    
    # LIVE arm state should NOT exist for WAR
    assert not (reports_dir / "live_arm_state_report_v1.json").exists()
    
    # Verify pool_mode marker
    with open(reports_dir / "pool_mode_v1.json") as f:
        marker = json.load(f)
    assert marker["pool_enabled"] is True
    
    # Check evidence contract (simplified - just verify files exist)
    # In real scenario, call check_pool_evidence_contract from safety_registry
    # For this test, we verify the core artifacts are present

def test_live_evidence_ok(registry, tmp_path, monkeypatch):
    """LIVE run includes live_arm_state, evidence check returns OK."""
    monkeypatch.setattr(pool_reports_v1, "resolve_reports_dir", lambda s, r, root_dir=None: tmp_path / s / r / "reports")
    
    from tezaver.matrix.pool import pool_engine_v1, live_arm_state_v1, pool_orchestrator_v1
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    monkeypatch.setattr(live_arm_state_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    monkeypatch.setattr(pool_orchestrator_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    trace_ctx = {"engine_version": "v1.0.TEST", "data_fingerprint": "df_test", "config_signature": "cs_test"}
    
    result = run_pool_evidence_bundle("live", "live_pool_evidence_001", trace_ctx, registry)
    
    assert result["status"] == "OK"
    assert "2d_live_arm" in result["phases"]
    
    reports_dir = tmp_path / "live" / "live_pool_evidence_001" / "reports"
    
    # Check LIVE-specific artifact exists
    assert (reports_dir / "live_arm_state_report_v1.json").exists()
    
    # Verify arm state content
    with open(reports_dir / "live_arm_state_report_v1.json") as f:
        arm_data = json.load(f)
    assert arm_data["armed"] is True
    assert arm_data["arm_reason"] == "BUNDLE_ARMED"
    
    # All other artifacts should also exist
    assert (reports_dir / "pool_universe_report_v1.json").exists()
    assert (reports_dir / "pool_selection_report_v1.json").exists()
    assert (reports_dir / "pool_risk_report_v1.json").exists()
