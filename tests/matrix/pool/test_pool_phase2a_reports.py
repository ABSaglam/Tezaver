import pytest
import shutil
from pathlib import Path
from tezaver.matrix.bundles.bundle_registry import BundleRegistry
from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1, LoadedBundle
from tezaver.matrix.pool import pool_engine_v1
from tezaver.matrix.pool.pool_engine_v1 import (
    build_universe_from_bundle_registry,
    build_intents,
    run_pool_phase2a
)

def create_bundle(bundle_id, symbol, tf, qc=50, trigger=None, policy=None):
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
        tier="TIER_1",
        trigger_spec_v1=trigger,
        policy_spec_v1=policy
    )
    return LoadedBundle(manifest, "/tmp", "LOADED_OK")

@pytest.fixture
def mock_registry():
    return BundleRegistry()

def test_universe_build(mock_registry):
    # Test Case 1: Universe build from registry
    # BTCUSDT 15m qc=88, ETHUSDT 1h qc=70
    b1 = create_bundle("btc_15m_1", "BTCUSDT", "15m", 88)
    b2 = create_bundle("eth_1h_1", "ETHUSDT", "1h", 70)
    b3 = create_bundle("btc_15m_curr", "BTCUSDT", "15m", 50) # Worse score
    
    mock_registry.add(b1)
    mock_registry.add(b2)
    mock_registry.add(b3)
    
    cells = build_universe_from_bundle_registry(mock_registry)
    
    assert len(cells) == 2
    
    btc = next(c for c in cells if c.symbol == "BTCUSDT")
    assert btc.timeframe == "15m"
    assert btc.best_bundle_id == "btc_15m_1" # 88 > 50
    assert len(btc.bundles_loaded_ok) == 2
    
    eth = next(c for c in cells if c.symbol == "ETHUSDT")
    assert eth.best_bundle_id == "eth_1h_1"

def test_intents_build(mock_registry):
    # Test Case 2: Intents build (specs present vs missing)
    
    trigger = {"type": "CLOSED_BAR_SIGNAL", "params": {}}
    policy = {"exit_policy": "ATR", "params": {}}
    
    # BTC bundle v2: specs present
    b_btc = create_bundle("btc_v2", "BTCUSDT", "15m", 90, trigger, policy)
    # ETH bundle v1: specs missing
    b_eth = create_bundle("eth_v1", "ETHUSDT", "1h", 80, None, None)
    
    mock_registry.add(b_btc)
    mock_registry.add(b_eth)
    
    cells = build_universe_from_bundle_registry(mock_registry)
    
    tick_ts = "2023-01-01T12:00:00Z"
    closed_bars = {"15m": tick_ts, "1h": tick_ts}
    
    intents, skipped_map = build_intents(cells, tick_ts, closed_bars, mock_registry)
    
    assert len(intents) == 2
    
    i_btc = next(i for i in intents if i.bundle_id == "btc_v2")
    assert i_btc.reason == "OK"
    assert i_btc.trigger_type == "CLOSED_BAR_SIGNAL"
    
    i_eth = next(i for i in intents if i.bundle_id == "eth_v1")
    assert i_eth.reason == "SKIPPED_NO_SPECS"
    assert i_eth.trigger_type == "NONE"
    
    assert skipped_map["SKIPPED_NO_SPECS"] == 1
    
    # Test with partial closed bars
    closed_bars_partial = {"15m": tick_ts}
    intents_p, _ = build_intents(cells, tick_ts, closed_bars_partial, mock_registry)
    # Only BTC (15m) should be generated
    assert len(intents_p) == 1
    assert intents_p[0].bundle_id == "btc_v2"

def test_run_execution(mock_registry, monkeypatch, tmp_path):
    # Test Case 3: Run writes reports to correct run-scoped path
    
    # Setup registry with 1 valid bundle
    trigger = {"type": "Signal", "params": {}}
    policy = {"exit_policy": "Fixed", "params": {}}
    b = create_bundle("b1", "SOLUSDT", "4h", 85, trigger, policy)
    mock_registry.add(b)
    
    # Patch resolve_reports_dir to use tmp dir
    def fake_resolve(stage, run_id, root_dir=None):
        return tmp_path / stage / run_id / "reports"
    
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", fake_resolve)
    
    trace_ctx = {
        "engine_version": "v1.0.TEST",
        "data_fingerprint": "df_TEST",
        "config_signature": "cs_TEST"
    }
    
    closed_bars = {"4h": "2023-09-09T09:00:00Z"}
    
    res = run_pool_phase2a("WAR", "run_test_01", mock_registry, trace_ctx, closed_bars)
    
    assert res["status"] == "OK"
    assert res["universe_cells"] == 1
    assert res["intents_created"] == 1
    
    reports_dir = tmp_path / "WAR" / "run_test_01" / "reports"
    assert reports_dir.exists()
    
    # Check Universe Report
    uni_file = reports_dir / "pool_universe_report_v1.json"
    assert uni_file.exists()
    # Check contents lightly? Content checked in file write if needed.
    
    # Check Tick Report
    tick_file = reports_dir / "pool_tick_report_v1.json"
    assert tick_file.exists()
    
    # Check Intents Report
    int_file = reports_dir / "pool_intents_report_v1.json"
    assert int_file.exists()
