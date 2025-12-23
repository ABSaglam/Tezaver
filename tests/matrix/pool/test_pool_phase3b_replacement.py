import pytest
from tezaver.matrix.pool.replacement_engine_v1 import evaluate_replacement
from tezaver.matrix.pool.pool_models_v1 import PoolSelectionItemV1

def create_selection_item(intent_id, rank_score=100.0, symbol="BTC", tf="1h", bundle_id="b1"):
    return PoolSelectionItemV1(
        intent_id=intent_id,
        symbol=symbol,
        timeframe=tf,
        bundle_id=bundle_id,
        qc_score=80,
        tier="GOLD",
        trigger_type="SIGNAL",
        exit_policy="ATR",
        rank_score=rank_score,
        rank_reason="qc+tier"
    )

def test_disabled_skipped():
    """Replacement disabled -> SKIPPED DISABLED."""
    report = evaluate_replacement(
        run_id="r1", stage="war", trace_ctx={},
        open_positions=[{"pos_id": "p1", "symbol": "BTC"}],
        selected_intents=[create_selection_item("i1", 100)],
        capacity=0, open_now=20, max_open_positions=20,
        reconcile_verdict="OK",
        config={"replacement_enabled": False}
    )
    assert report.verdict == "SKIPPED"
    assert report.skip_reason == "DISABLED"

def test_capacity_available_skipped():
    """Capacity > 0 -> SKIPPED CAPACITY_AVAILABLE."""
    report = evaluate_replacement(
        run_id="r2", stage="war", trace_ctx={},
        open_positions=[{"pos_id": "p1", "symbol": "BTC"}],
        selected_intents=[create_selection_item("i1", 100)],
        capacity=15, open_now=5, max_open_positions=20,
        reconcile_verdict="OK",
        config={"replacement_enabled": True}
    )
    assert report.verdict == "SKIPPED"
    assert report.skip_reason == "CAPACITY_AVAILABLE"

def test_drift_skipped():
    """Drift detected -> SKIPPED DRIFT."""
    report = evaluate_replacement(
        run_id="r3", stage="war", trace_ctx={},
        open_positions=[{"pos_id": "p1", "symbol": "BTC"}],
        selected_intents=[create_selection_item("i1", 100)],
        capacity=0, open_now=20, max_open_positions=20,
        reconcile_verdict="NEEDS_SAFE_MODE",
        config={"replacement_enabled": True}
    )
    assert report.verdict == "SKIPPED"
    assert report.skip_reason == "DRIFT"

def test_suggested_replacement():
    """Capacity=0 and delta>=min_delta -> SUGGESTED."""
    # Worst position score = 70 (qc=50 + no tier bonus)
    worst_pos = {"pos_id": "weak_pos", "symbol": "WEAK", "qc_score": 50, "tier": None}
    # Best intent score = 100
    best_intent = create_selection_item("strong_intent", rank_score=100)
    # Delta = 100 - 50 = 50 >= 15 (default min_delta)
    
    report = evaluate_replacement(
        run_id="r4", stage="war", trace_ctx={},
        open_positions=[worst_pos],
        selected_intents=[best_intent],
        capacity=0, open_now=20, max_open_positions=20,
        reconcile_verdict="OK",
        config={"replacement_enabled": True, "replacement_min_delta": 15.0, "replacement_min_rank": 90.0}
    )
    assert report.verdict == "SUGGESTED"
    assert report.candidate is not None
    assert report.candidate.replace_out_pos_id == "weak_pos"
    assert report.candidate.replace_in_intent_id == "strong_intent"
    assert report.candidate.delta_score == 50.0
    assert report.candidate.requires_human_confirm is True

def test_not_better_skipped():
    """Delta < min_delta -> SKIPPED NO_BETTER_THAN_WORST."""
    # Worst position score = 90
    worst_pos = {"pos_id": "ok_pos", "symbol": "OK", "qc_score": 90, "tier": None}
    # Best intent score = 100 -> delta = 10 < 15
    best_intent = create_selection_item("intent", rank_score=100)
    
    report = evaluate_replacement(
        run_id="r5", stage="war", trace_ctx={},
        open_positions=[worst_pos],
        selected_intents=[best_intent],
        capacity=0, open_now=20, max_open_positions=20,
        reconcile_verdict="OK",
        config={"replacement_enabled": True, "replacement_min_delta": 15.0}
    )
    assert report.verdict == "SKIPPED"
    assert report.skip_reason == "NO_BETTER_THAN_WORST"
