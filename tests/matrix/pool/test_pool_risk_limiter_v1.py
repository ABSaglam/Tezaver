import pytest
from tezaver.matrix.pool.pool_risk_limiter_v1 import (
    apply_limits,
    build_risk_report_v2,
    DEFAULT_GLOBAL_NOTIONAL_CAP,
    DEFAULT_PER_COIN_NOTIONAL_CAP
)

def make_intent(intent_id: str, symbol: str, rank_score: float, notional: float = 100.0):
    return {
        "intent_id": intent_id,
        "symbol": symbol,
        "rank_score": rank_score,
        "notional": notional
    }

def test_global_cap_trims_weakest():
    """Global cap trims weakest intents first."""
    # portfolio_open=1900, cap=2000, room=100
    # 3 intents with 100 each = 300 total, overflow 200
    intents = [
        make_intent("int_strong", "BTC", rank_score=120, notional=100),
        make_intent("int_mid", "ETH", rank_score=110, notional=100),
        make_intent("int_weak", "SOL", rank_score=90, notional=100)
    ]
    
    result = apply_limits(
        selected_intents=intents,
        portfolio_open_notional=1900.0,
        coin_open_notional={},
        global_notional_cap=2000.0,
        per_coin_notional_cap=500.0  # high to not interfere
    )
    
    # Should block weakest (90) + mid (110) to cover 200 overflow
    assert result.blocked_reasons_count.get("GLOBAL_NOTIONAL_CAP", 0) == 2
    blocked_ids = {b["intent_id"] for b in result.blocked}
    assert "int_weak" in blocked_ids
    assert "int_mid" in blocked_ids
    assert "int_strong" not in blocked_ids
    
    assert len(result.allowed) == 1
    assert result.allowed[0]["intent_id"] == "int_strong"

def test_per_coin_cap_blocks_overflow():
    """Per-coin cap blocks when symbol exceeds limit."""
    # per_coin_cap=200, SOL already has 150 open
    intents = [
        make_intent("sol_new", "SOL", rank_score=100, notional=100),  # 150+100=250 > 200
        make_intent("btc_new", "BTC", rank_score=100, notional=100)   # 0+100=100 <= 200
    ]
    
    result = apply_limits(
        selected_intents=intents,
        portfolio_open_notional=150.0,
        coin_open_notional={"SOL": 150.0},
        global_notional_cap=2000.0,
        per_coin_notional_cap=200.0
    )
    
    assert result.blocked_reasons_count.get("PER_COIN_CAP", 0) == 1
    blocked_ids = {b["intent_id"] for b in result.blocked}
    assert "sol_new" in blocked_ids
    allowed_ids = {a["intent_id"] for a in result.allowed}
    assert "btc_new" in allowed_ids

def test_deterministic_order():
    """Same inputs produce same blocked list."""
    intents = [
        make_intent("a", "BTC", rank_score=100, notional=100),
        make_intent("b", "BTC", rank_score=100, notional=100),  # same score
        make_intent("c", "BTC", rank_score=100, notional=100)
    ]
    
    result1 = apply_limits(
        selected_intents=intents,
        portfolio_open_notional=0,
        coin_open_notional={},
        global_notional_cap=2000.0,
        per_coin_notional_cap=200.0  # Only 2 can fit
    )
    
    result2 = apply_limits(
        selected_intents=intents,
        portfolio_open_notional=0,
        coin_open_notional={},
        global_notional_cap=2000.0,
        per_coin_notional_cap=200.0
    )
    
    # Same blocked ids
    blocked_ids1 = [b["intent_id"] for b in result1.blocked]
    blocked_ids2 = [b["intent_id"] for b in result2.blocked]
    assert blocked_ids1 == blocked_ids2

def test_kill_switch_blocks_all():
    """Kill switch blocks everything."""
    intents = [
        make_intent("a", "BTC", rank_score=100, notional=100),
        make_intent("b", "ETH", rank_score=100, notional=100)
    ]
    
    result = apply_limits(
        selected_intents=intents,
        portfolio_open_notional=0,
        kill_switch_triggered=True
    )
    
    assert len(result.allowed) == 0
    assert len(result.blocked) == 2
    assert result.blocked_reasons_count.get("KILL_SWITCH", 0) == 2
