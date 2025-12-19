# Tezaver Bulut - Decider Pipeline Tests
"""
Tests for decider logic including allowlists and limits.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.engine.decider import Decider
from tezaver.bulut.schemas.ranking_snapshot_v1 import RankingSnapshotV1, CandidateScore

def _create_candidate(symbol, score):
    return CandidateScore(symbol, score, {}, [])

def _create_ranking(candidates):
    return RankingSnapshotV1(
        datetime.now(timezone.utc), "15m", [], len(candidates), 70, 20, candidates
    )

def _make_mock_ctx(config):
    """Create mock context for Decider with required attributes."""
    ctx = MagicMock()
    ctx.config = config
    ctx.policy = MagicMock()
    ctx.policy.transition_on_open_submit = MagicMock()
    ctx.entry_sizing_resolver = MagicMock()
    # Default sizing: not blocked, 100 USDT notional
    ctx.entry_sizing_resolver.resolve.return_value = MagicMock(
        blocked=False, 
        notional_usdt=100, 
        profile_id="test", 
        explain="test",
        leverage=None,
        block_reason=None
    )
    return ctx

def test_decider_blocked_if_pattern_pack_missing():
    """Should return empty list if pattern pack not loaded."""
    config = BulutConfig()
    ctx = _make_mock_ctx(config)
    decider = Decider(ctx)
    
    ranking = _create_ranking([_create_candidate("BTCUSDT", 90)])
    
    plans = decider.decide(ranking, 0, 0, pattern_pack_loaded=False)
    assert len(plans) == 0

def test_decider_allowlist_block():
    """Should block symbols not in allowlist."""
    config = BulutConfig(trade_min_score=50)
    ctx = _make_mock_ctx(config)
    decider = Decider(ctx)
    
    ranking = _create_ranking([
        _create_candidate("BTCUSDT", 80), # Allowed
        _create_candidate("SHITCOIN", 80) # Not allowed
    ])
    
    allowlist = {"BTCUSDT"}
    
    plans = decider.decide(ranking, 0, 0, True, allowlist=allowlist)
    
    assert len(plans) == 2
    
    p1 = next(p for p in plans if p.symbol == "BTCUSDT")
    assert p1.decision.name == "OPEN"
    
    p2 = next(p for p in plans if p.symbol == "SHITCOIN")
    assert p2.decision.name == "SKIP"
    assert p2.reasons["skip_reason"] == "ALLOWLIST_BLOCK"

def test_decider_max_new_entries_per_cycle():
    """Should respect max new entries limit per cycle."""
    config = BulutConfig(max_new_entries_per_cycle=1, trade_min_score=50)
    ctx = _make_mock_ctx(config)
    decider = Decider(ctx)
    
    ranking = _create_ranking([
        _create_candidate("A", 90),
        _create_candidate("B", 85)
    ])
    
    plans = decider.decide(ranking, 0, 0, True, allowlist=None)
    
    # Should contain 2 plans: 1 OPEN, 1 SKIP (Limit Reached)
    assert len(plans) == 2
    
    open_plans = [p for p in plans if p.decision.name == "OPEN"]
    skip_plans = [p for p in plans if p.decision.name == "SKIP"]
    
    assert len(open_plans) == 1
    assert open_plans[0].symbol == "A" # Higher score wins
    
    assert len(skip_plans) == 1
    assert skip_plans[0].symbol == "B"
    assert skip_plans[0].reasons["skip_reason"] == "CYCLE_ENTRY_LIMIT_REACHED"

def test_decider_global_max_positions():
    """Should block if max open positions reached."""
    config = BulutConfig(max_open_positions=2)
    ctx = _make_mock_ctx(config)
    decider = Decider(ctx)
    
    ranking = _create_ranking([_create_candidate("A", 90)])
    
    # 2 positions already open
    plans = decider.decide(ranking, open_positions_count=2, total_notional=0, pattern_pack_loaded=True)
    
    assert len(plans) == 1
    assert plans[0].decision.name == "SKIP"
    assert plans[0].reasons["skip_reason"] == "MAX_POSITIONS_REACHED"
