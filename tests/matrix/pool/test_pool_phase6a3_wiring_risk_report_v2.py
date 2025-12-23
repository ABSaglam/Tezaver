import pytest
from unittest.mock import MagicMock, patch
from tezaver.matrix.pool.pool_engine_v1 import run_pool_phase2c
from tezaver.matrix.pool.pool_models_v1 import PoolSelectionItemV1
from tezaver.matrix.pool.pool_risk_limiter_v1 import DEFAULT_GLOBAL_NOTIONAL_CAP

# Mock BundleRegistry
class MockRegistry:
    def get_bundle(self, bundle_id):
        return MagicMock()

def test_phase2c_generates_v1_and_v2_reports(tmp_path):
    """Phase 2C should generate both V1 and V2 risk reports."""
    run_id = "test_run_v2"
    stage = "war"
    reports_dir = tmp_path / "out" / "matrix_runs" / stage / run_id / "reports"
    reports_dir.mkdir(parents=True)
    
    # Trace context
    trace_ctx = {
        "engine_version": "vTest",
        "data_fingerprint": "DF",
        "config_signature": "CS"
    }
    
    # Selected items (within limits)
    # Create items and dynamic attach proposed_notional (as Engine expects it)
    i1 = PoolSelectionItemV1(
        intent_id="i1", symbol="BTC", timeframe="1h", bundle_id="b1",
        rank_score=100, trigger_type="S", exit_policy="F",
        qc_score=100, tier="T1", rank_reason="test"
    )
    i1.proposed_notional = 100.0
    i1.stop_type = "F"
    i1.meta = {}
    
    items = [i1]
    
    # Patch resolve_reports_dir to use tmp_path
    with patch("tezaver.matrix.pool.pool_engine_v1.resolve_reports_dir", return_value=reports_dir):
        result = run_pool_phase2c(
            stage=stage,
            run_id=run_id,
            trace_ctx=trace_ctx,
            selected_items=items,
            registry=MockRegistry(),
            global_limits={"max_total_notional": 2000.0}
        )
        
    assert result["status"] == "OK"
    assert (reports_dir / "pool_risk_report_v1.json").exists()
    assert (reports_dir / "pool_risk_report_v2.json").exists()
    
def test_global_cap_trim_in_engine(tmp_path):
    """Engine should apply global cap trimming deterministically."""
    run_id = "test_run_trim"
    stage = "war"
    reports_dir = tmp_path / "out" / "matrix_runs" / stage / run_id / "reports"
    reports_dir.mkdir(parents=True)
    
    # Use Portfolio Provider to inject high open notional
    # For now we rely on the fact that provider defaults to 0 if not found
    # But we set limits low to force trimming
    
    limits = {"max_total_notional": 150.0} # Only 150 allowed
    
    i_strong = PoolSelectionItemV1(
        intent_id="strong", symbol="BTC", timeframe="1h", bundle_id="b1",
        rank_score=120, trigger_type="S", exit_policy="F",
        qc_score=100, tier="T1", rank_reason="test"
    )
    i_strong.proposed_notional = 100.0
    i_strong.stop_type = "F"
    i_strong.meta = {}

    i_weak = PoolSelectionItemV1(
        intent_id="weak", symbol="ETH", timeframe="1h", bundle_id="b2",
        rank_score=90, trigger_type="S", exit_policy="F",
        qc_score=100, tier="T2", rank_reason="test"
    )
    i_weak.proposed_notional = 100.0
    i_weak.stop_type = "F"
    i_weak.meta = {}
    
    items = [i_strong, i_weak]
    
    with patch("tezaver.matrix.pool.pool_engine_v1.resolve_reports_dir", return_value=reports_dir):
        result = run_pool_phase2c(
            stage=stage,
            run_id=run_id,
            trace_ctx={},
            selected_items=items,
            registry=MockRegistry(),
            global_limits=limits
        )
        
    # Total needed 200 > 150 cap. Should trim weakest (90).
    assert result["allowed_count"] == 1
    assert result["blocked_count"] == 1
    
    import json
    with open(reports_dir / "pool_risk_report_v2.json") as f:
        v2 = json.load(f)
        
    blocked_ids = [b["intent_id"] for b in v2["blocked"]]
    assert "weak" in blocked_ids
    assert "strong" not in blocked_ids
    assert v2["blocked_reasons_count"]["GLOBAL_NOTIONAL_CAP"] == 1
