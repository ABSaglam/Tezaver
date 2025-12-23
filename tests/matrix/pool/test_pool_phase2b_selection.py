import pytest
import shutil
from pathlib import Path
from tezaver.matrix.pool import pool_models_v1
from tezaver.matrix.pool.pool_models_v1 import TradeIntentV1
from tezaver.matrix.pool.portfolio_provider_v1 import StubPortfolioProviderV1
from tezaver.matrix.pool.pool_engine_v1 import run_pool_phase2b
from tezaver.matrix.pool import pool_engine_v1

# Helper to create intent
def create_intent(intent_id, qc=None, tier=None, reason="OK"):
    return TradeIntentV1(
        intent_id=intent_id,
        symbol="SYM",
        timeframe="TF",
        bundle_id=f"b_{intent_id}",
        trigger_type="SIGNAL",
        exit_policy="ATR",
        created_ts_iso="2023-01-01T00:00:00Z",
        reason=reason,
        qc_score=qc,
        tier=tier
    )

def test_capacity_calc(tmp_path, monkeypatch):
    """Test capacity calculation logic."""
    # Stub provider with 5 positions
    provider = StubPortfolioProviderV1(open_positions=[{"id": i} for i in range(5)])
    
    trace_ctx = {"engine_version": "v1"}
    
    # Mock resolve_reports_dir
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    # Case 1: Max 20 -> Cap 15
    res = run_pool_phase2b("WAR", "run_cap_15", trace_ctx, [], provider, max_open_positions=20)
    assert res["capacity"] == 15
    
    # Case 2: Max 3 -> Cap 0 (saturated)
    res = run_pool_phase2b("WAR", "run_cap_0", trace_ctx, [], provider, max_open_positions=3)
    assert res["capacity"] == 0 # 3 - 5 < 0 -> 0

def test_deterministic_ranking(tmp_path, monkeypatch):
    """Test deterministic selection (QC + Tier)."""
    # 3 Intents
    # A: QC 90 + DIAMOND(30) = 120
    # B: QC 95 + None(0) = 95
    # C: QC 80 + GOLD(20) = 100
    
    i_a = create_intent("A", 90, "DIAMOND")
    i_b = create_intent("B", 95, None)
    i_c = create_intent("C", 80, "GOLD")
    
    # Provider empty -> full capacity
    provider = StubPortfolioProviderV1(open_positions=[])
    
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    trace_ctx = {"engine_version": "v1"}
    
    # Select Top 2
    res = run_pool_phase2b("WAR", "run_rank", trace_ctx, [i_a, i_b, i_c], provider, max_open_positions=2)
    
    assert res["selected"] == 2
    
    report_file = tmp_path / "WAR" / "run_rank" / "reports" / "pool_selection_report_v1.json"
    import json
    with open(report_file) as f:
        data = json.load(f)
        
    selected = data["selected"]
    # Expect Order: A (120), C (100) -> B (95) skipped
    assert selected[0]["intent_id"] == "A"
    assert selected[0]["rank_score"] == 120.0
    
    assert selected[1]["intent_id"] == "C"
    assert selected[1]["rank_score"] == 100.0
    
    skipped = data["skipped"]
    assert len(skipped) == 1
    assert skipped[0]["intent_id"] == "B"
    assert skipped[0]["reason"] == "SKIPPED_OVERFLOW"

def test_tie_breaking(tmp_path, monkeypatch):
    """Test tie-breaking by Intent ID ASC."""
    # A: QC 90
    # B: QC 90
    
    i_b = create_intent("intent_B", 90)
    i_a = create_intent("intent_A", 90) # Should come first due to ID 'intent_A' < 'intent_B'
    
    provider = StubPortfolioProviderV1()
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    # Select Top 1
    res = run_pool_phase2b("WAR", "run_tie", {}, [i_b, i_a], provider, max_open_positions=1)
    
    report_file = tmp_path / "WAR" / "run_tie" / "reports" / "pool_selection_report_v1.json"
    import json
    with open(report_file) as f:
        data = json.load(f)
        
    selected = data["selected"]
    assert selected[0]["intent_id"] == "intent_A"

def test_skipped_aggregation(tmp_path, monkeypatch):
    """Test aggregation of skipped reasons."""
    i_ok = create_intent("ok", 90)
    i_skip = create_intent("skip", reason="SKIPPED_NO_SPECS")
    
    provider = StubPortfolioProviderV1()
    monkeypatch.setattr(pool_engine_v1, "resolve_reports_dir", lambda s, r: tmp_path / s / r / "reports")
    
    res = run_pool_phase2b("WAR", "run_skip", {}, [i_ok, i_skip], provider, max_open_positions=10)
    
    report_file = tmp_path / "WAR" / "run_skip" / "reports" / "pool_selection_report_v1.json"
    import json
    with open(report_file) as f:
        data = json.load(f)
        
    assert data["intents_considered"] == 2
    assert data["intents_eligible"] == 1
    assert data["selected_count"] == 1
    
    reasons = data["skipped_reasons_count"]
    assert reasons["SKIPPED_NO_SPECS"] == 1
