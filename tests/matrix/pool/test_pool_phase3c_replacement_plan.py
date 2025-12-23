import pytest
from tezaver.matrix.pool.replacement_plan_engine_v1 import build_replacement_plan

def test_no_suggested_replacement_skipped():
    """No suggested replacement -> SKIPPED."""
    replacement_report = {"verdict": "SKIPPED", "enabled": True}
    reconcile_report = {"verdict": "OK"}
    
    report = build_replacement_plan(
        run_id="r1", stage="war", trace_ctx={},
        replacement_report=replacement_report,
        reconcile_report=reconcile_report
    )
    
    assert report.replacement_verdict == "SKIPPED"
    assert report.skip_reason == "NO_REPLACEMENT"
    assert report.close_plan is None
    assert report.open_plan is None

def test_suggested_creates_plan():
    """Suggested replacement -> plan created with CLOSE then OPEN."""
    replacement_report = {
        "verdict": "SUGGESTED",
        "enabled": True,
        "candidate": {
            "replace_out_pos_id": "pos_weak_1",
            "replace_out_symbol": "WEAK",
            "replace_in_intent_id": "intent_strong_1",
            "replace_in_bundle_id": "bundle_abc",
            "replace_in_symbol": "STRONG",
            "replace_in_timeframe": "1h"
        }
    }
    reconcile_report = {"verdict": "OK"}
    
    report = build_replacement_plan(
        run_id="r2", stage="war", trace_ctx={},
        replacement_report=replacement_report,
        reconcile_report=reconcile_report,
        config={"default_notional": 150.0}
    )
    
    assert report.replacement_verdict == "SUGGESTED"
    assert report.skip_reason is None
    assert report.close_plan is not None
    assert report.open_plan is not None
    
    # Check close plan
    assert report.close_plan.action == "CLOSE_POSITION"
    assert report.close_plan.pos_id == "pos_weak_1"
    assert report.close_plan.close_mode == "MARKET_DRYRUN"
    
    # Check open plan
    assert report.open_plan.action == "OPEN_POSITION"
    assert report.open_plan.intent_id == "intent_strong_1"
    assert report.open_plan.notional == 150.0
    assert report.open_plan.open_mode == "MARKET_DRYRUN"
    
    # Check atomic order
    assert report.atomic_order == ["CLOSE_POSITION", "OPEN_POSITION"]
    assert report.requires_human_confirm is True

def test_drift_skipped():
    """Drift detected -> SKIPPED DRIFT."""
    replacement_report = {
        "verdict": "SUGGESTED",
        "enabled": True,
        "candidate": {"replace_out_pos_id": "pos1", "replace_in_intent_id": "i1"}
    }
    reconcile_report = {"verdict": "NEEDS_SAFE_MODE"}
    
    report = build_replacement_plan(
        run_id="r3", stage="war", trace_ctx={},
        replacement_report=replacement_report,
        reconcile_report=reconcile_report
    )
    
    assert report.skip_reason == "DRIFT"
    assert report.close_plan is None

def test_policy_spec_copied():
    """Policy spec from bundle is copied if present."""
    from tezaver.matrix.bundles.bundle_registry import BundleRegistry
    from tezaver.matrix.bundles.bundle_models_v1 import ApprovedRallyBundleManifestV1, LoadedBundle
    
    manifest = ApprovedRallyBundleManifestV1(
        bundle_version="approved_rally_bundle_v1",
        bundle_id="bundle_policy_test",
        symbol="BTCUSDT",
        timeframe="1h",
        event_id="evt_1",
        event_time_iso="2023-01-01T00:00:00Z",
        approved_entry_bar_offset=10,
        approved_entry_ts="2023-01-01T00:00:00Z",
        qc_verdict="PASS",
        qc_score=85,
        tier="GOLD",
        policy_spec_v1={"exit_policy": "ATR", "params": {"atr_mult": 2.5}}
    )
    bundle = LoadedBundle(manifest, "/tmp", "LOADED_OK")
    
    registry = BundleRegistry()
    registry.add(bundle)
    
    replacement_report = {
        "verdict": "SUGGESTED",
        "enabled": True,
        "candidate": {
            "replace_out_pos_id": "pos1",
            "replace_out_symbol": "OLD",
            "replace_in_intent_id": "intent1",
            "replace_in_bundle_id": "bundle_policy_test",
            "replace_in_symbol": "BTCUSDT",
            "replace_in_timeframe": "1h"
        }
    }
    reconcile_report = {"verdict": "OK"}
    
    report = build_replacement_plan(
        run_id="r4", stage="war", trace_ctx={},
        replacement_report=replacement_report,
        reconcile_report=reconcile_report,
        bundle_registry=registry
    )
    
    assert report.open_plan is not None
    assert report.open_plan.policy_spec == {"exit_policy": "ATR", "params": {"atr_mult": 2.5}}
