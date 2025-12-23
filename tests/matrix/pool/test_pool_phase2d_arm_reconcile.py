import pytest
from pathlib import Path
import json
from tezaver.matrix.pool.reconcile_provider_v1 import StubOpenPositionsProviderV1
from tezaver.matrix.pool.pool_engine_v1 import (
    run_pool_phase2d_live_arm,
    run_pool_phase2d_restart_reconcile
)
from tezaver.matrix.pool import pool_engine_v1, live_arm_state_v1

def test_live_arm_report_writes(tmp_path, monkeypatch):
    """Verify arm report creation with required fields."""
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    monkeypatch.setattr(live_arm_state_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    arm_state = {
        "armed": True,
        "arm_reason": "BUNDLE_ARMED",
        "bundle_id": "bundle_abc",
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "qc_score": 85,
        "tier": "GOLD",
        "notes": ["test_arm"]
    }
    
    res = run_pool_phase2d_live_arm("live", "live_pool_001", {}, arm_state)
    
    assert res["status"] == "OK"
    assert res["armed"] is True
    
    report_path = tmp_path / "live" / "live_pool_001" / "reports" / "live_arm_state_report_v1.json"
    assert report_path.exists()
    
    with open(report_path) as f:
        data = json.load(f)
    
    # Required fields
    assert "run_id" in data
    assert "engine_version" in data
    assert "data_fingerprint" in data
    assert "config_signature" in data
    assert "built_ts_iso" in data
    assert "arm_id" in data
    assert data["armed"] is True
    assert data["arm_reason"] == "BUNDLE_ARMED"
    assert data["bundle_id"] == "bundle_abc"

def test_reconcile_ok_when_same(tmp_path, monkeypatch):
    """Verify OK verdict when snapshots are identical."""
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    positions = [
        {"pos_id": "A", "symbol": "BTC"},
        {"pos_id": "B", "symbol": "ETH"}
    ]
    
    before_provider = StubOpenPositionsProviderV1(positions)
    after_provider = StubOpenPositionsProviderV1(positions)
    
    res = run_pool_phase2d_restart_reconcile("war", "war_rec_001", {}, before_provider, after_provider)
    
    assert res["status"] == "OK"
    assert res["verdict"] == "OK"
    assert res["changed"] is False
    
    report_path = tmp_path / "war" / "war_rec_001" / "reports" / "restart_reconcile_report_v1.json"
    with open(report_path) as f:
        data = json.load(f)
    
    assert data["drift"]["delta_count"] == 0
    assert data["drift"]["missing_ids"] == []
    assert data["drift"]["extra_ids"] == []

def test_reconcile_drift_needs_safe_mode(tmp_path, monkeypatch):
    """Verify NEEDS_SAFE_MODE when drift detected."""
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    before_positions = [
        {"pos_id": "A", "symbol": "BTC"},
        {"pos_id": "B", "symbol": "ETH"}
    ]
    after_positions = [
        {"pos_id": "A", "symbol": "BTC"},
        {"pos_id": "B", "symbol": "ETH"},
        {"pos_id": "C", "symbol": "SOL"}  # New position
    ]
    
    before_provider = StubOpenPositionsProviderV1(before_positions)
    after_provider = StubOpenPositionsProviderV1(after_positions)
    
    res = run_pool_phase2d_restart_reconcile("live", "live_rec_drift", {}, before_provider, after_provider)
    
    assert res["verdict"] == "NEEDS_SAFE_MODE"
    assert res["changed"] is True
    
    report_path = tmp_path / "live" / "live_rec_drift" / "reports" / "restart_reconcile_report_v1.json"
    with open(report_path) as f:
        data = json.load(f)
    
    assert data["drift"]["changed"] is True
    assert data["drift"]["delta_count"] == 1
    assert "C" in data["drift"]["extra_ids"]
    assert "ENTER_SAFE_MODE" in data["suggested_actions"]
