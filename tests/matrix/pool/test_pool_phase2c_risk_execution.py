import pytest
from pathlib import Path
import json
from tezaver.matrix.bundles.bundle_registry import BundleRegistry
from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1, LoadedBundle
from tezaver.matrix.pool.pool_models_v1 import PoolSelectionItemV1
from tezaver.matrix.pool.pool_engine_v1 import run_pool_phase2c
from tezaver.matrix.pool import pool_engine_v1

# Helper to create selection item
def create_selection_item(intent_id, qc=80, tier="GOLD", bundle_id=None, rank_score=100.0):
    return PoolSelectionItemV1(
        intent_id=intent_id,
        symbol="BTCUSDT",
        timeframe="1h",
        bundle_id=bundle_id or f"b_{intent_id}",
        qc_score=qc,
        tier=tier,
        trigger_type="SIGNAL",
        exit_policy="ATR",
        rank_score=rank_score,
        rank_reason="qc+tier"
    )

# Helper to create bundle
def create_bundle(bundle_id, policy_spec=None):
    manifest = ApprovedRallyBundleManifestV1(
        bundle_version="approved_rally_bundle_v1",
        bundle_id=bundle_id,
        symbol="BTCUSDT",
        timeframe="1h",
        event_id="evt_1",
        event_time_iso="2023-01-01T00:00:00Z",
        approved_entry_bar_offset=10,
        approved_entry_ts="2023-01-01T00:00:00Z",
        qc_verdict="PASS",
        qc_score=80,
        tier="GOLD",
        trigger_spec_v1={"type": "SIGNAL"},
        policy_spec_v1=policy_spec
    )
    return LoadedBundle(manifest, "/tmp", "LOADED_OK")

@pytest.fixture
def registry():
    return BundleRegistry()

def test_missing_policy_blocks(registry, tmp_path, monkeypatch):
    """Bundle without policy_spec -> BLOCK MISSING_POLICY."""
    # Bundle V1 (no policy)
    b_v1 = create_bundle("b_v1", policy_spec=None)
    # Bundle V2 (with policy)
    b_v2 = create_bundle("b_v2", policy_spec={"exit_policy": "ATR", "params": {"atr_mult": 2.0, "notional": 100}})
    
    registry.add(b_v1)
    registry.add(b_v2)
    
    selected = [
        create_selection_item("i_v1", bundle_id="b_v1"),
        create_selection_item("i_v2", bundle_id="b_v2")
    ]
    
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    res = run_pool_phase2c("WAR", "run_risk", {}, selected, registry)
    
    assert res["status"] == "OK"
    assert res["allowed"] == 1
    assert res["blocked"] == 1
    
    risk_file = tmp_path / "WAR" / "run_risk" / "reports" / "pool_risk_report_v1.json"
    with open(risk_file) as f:
        data = json.load(f)
    
    assert data["blocked_reasons_count"]["MISSING_POLICY"] == 1
    
    # Check items
    items = data["items"]
    blocked_item = next(i for i in items if i["verdict"] == "BLOCK")
    assert blocked_item["block_reason"] == "MISSING_POLICY"

def test_kill_switch_blocks_all(registry, tmp_path, monkeypatch):
    """Kill switch triggered -> all intents BLOCK."""
    b = create_bundle("b_ok", policy_spec={"exit_policy": "ATR", "params": {}})
    registry.add(b)
    
    selected = [
        create_selection_item("i1", bundle_id="b_ok"),
        create_selection_item("i2", bundle_id="b_ok")
    ]
    
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    res = run_pool_phase2c("WAR", "run_kill", {}, selected, registry, kill_switch_triggered=True)
    
    assert res["allowed"] == 0
    assert res["blocked"] == 2
    
    risk_file = tmp_path / "WAR" / "run_kill" / "reports" / "pool_risk_report_v1.json"
    with open(risk_file) as f:
        data = json.load(f)
    
    assert data["blocked_reasons_count"]["KILL_SWITCH"] == 2
    assert data["kill_switch"]["triggered"] is True

def test_global_notional_limit_trims(registry, tmp_path, monkeypatch):
    """Global notional limit trims lower-ranked intents."""
    # 3 intents, each requests 3000 notional
    # Limit is 6000 -> only top 2 by rank_score fit
    
    for i in range(3):
        b = create_bundle(f"b_{i}", policy_spec={"exit_policy": "FIXED", "params": {"notional": 3000}})
        registry.add(b)
    
    selected = [
        create_selection_item("i_high", bundle_id="b_0", rank_score=120),
        create_selection_item("i_mid", bundle_id="b_1", rank_score=100),
        create_selection_item("i_low", bundle_id="b_2", rank_score=80)  # This should be trimmed
    ]
    
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    limits = {"max_total_notional": 6000.0, "per_coin_max_notional": 5000.0}
    res = run_pool_phase2c("WAR", "run_notional", {}, selected, registry, global_limits=limits)
    
    # Top 2 fit (3000 + 3000 = 6000), third is blocked
    assert res["allowed"] == 2
    assert res["blocked"] == 1
    
    risk_file = tmp_path / "WAR" / "run_notional" / "reports" / "pool_risk_report_v1.json"
    with open(risk_file) as f:
        data = json.load(f)
    
    assert data["blocked_reasons_count"]["GLOBAL_NOTIONAL_LIMIT"] == 1
    
    # Check the blocked one is the lowest ranked
    blocked_items = [i for i in data["items"] if i["verdict"] == "BLOCK"]
    assert blocked_items[0]["intent_id"] == "i_low"

def test_execution_summary_dry_run(registry, tmp_path, monkeypatch):
    """Verify execution summary is written in DRY_RUN mode."""
    b = create_bundle("b_exec", policy_spec={"exit_policy": "TRAILING", "params": {"trailing_pct": 0.03}})
    registry.add(b)
    
    selected = [create_selection_item("i_exec", bundle_id="b_exec")]
    
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    res = run_pool_phase2c("WAR", "run_exec", {}, selected, registry)
    
    assert res["mode"] == "DRY_RUN"
    
    exec_file = tmp_path / "WAR" / "run_exec" / "reports" / "pool_execution_summary_v1.json"
    with open(exec_file) as f:
        data = json.load(f)
    
    assert data["mode"] == "DRY_RUN"
    assert data["planned_orders"] == 1
    
    plan = data["plan"]
    assert len(plan) == 1
    assert plan[0]["action"] == "PLACE_ORDER"
    assert "dry_run" in plan[0]["notes"]
