# Tezaver Bulut - Trade Lock Tests
"""
Tests for trade lock behavior when PatternPack is missing.
"""

import pytest
import tempfile
import os


def test_trade_locked_when_pattern_pack_missing():
    """Trade should be locked when no pattern pack is loaded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SQLITE_PATH"] = os.path.join(tmpdir, "test.db")
        os.environ["NDJSON_PATH"] = os.path.join(tmpdir, "events.ndjson")
        os.environ["PATTERN_PACK_DIR"] = os.path.join(tmpdir, "packs")  # Empty dir
        
        from tezaver.bulut.core.context import bootstrap_context
        from tezaver.bulut.core.config import reload_config
        
        reload_config()
        ctx = bootstrap_context()
        
        # Try to load pattern pack (should fail - no files)
        result = ctx.load_pattern_pack()
        
        assert result is False
        assert ctx.state.pattern_pack_loaded is False
        assert ctx.state.trade_locked is True
        assert ctx.state.trade_lock_reason == "PATTERN_PACK_MISSING"


def test_decider_blocks_open_when_locked():
    """Decider should produce SKIP plans when trade is locked."""
    from tezaver.bulut.core.config import BulutConfig
    from tezaver.bulut.engine.decider import run_decider
    from tezaver.bulut.schemas.ranking_snapshot_v1 import (
        RankingSnapshotV1,
        CandidateScore,
    )
    from datetime import datetime, timezone
    
    config = BulutConfig()
    
    # Create ranking with one candidate
    ranking = RankingSnapshotV1(
        cycle_ts=datetime.now(timezone.utc),
        base_tf="15m",
        derived_tfs=["1h", "4h"],
        universe_size=1,
        threshold=70,
        topk=20,
        candidates=[
            CandidateScore(
                symbol="BTCUSDT",
                score=85.0,
                components={"pattern": 60, "trend": 15, "risk": 10},
                flags=["PATTERN_MATCH"],
            )
        ],
    )
    
    # Run decider with trade locked
    plans = run_decider(
        config=config,
        ranking=ranking,
        trade_locked=True,
        lock_reason="PATTERN_PACK_MISSING",
    )
    
    assert len(plans) == 1
    plan = plans[0]
    
    assert plan.symbol == "BTCUSDT"
    assert plan.decision.value == "SKIP"
    assert plan.reasons.get("skip_reason") == "TRADE_LOCKED"
    assert plan.reasons.get("lock_reason") == "PATTERN_PACK_MISSING"


def test_trade_unlocked_when_pattern_pack_loaded():
    """Trade should be unlocked when pattern pack is loaded."""
    import json
    from datetime import datetime, timezone
    
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["SQLITE_PATH"] = os.path.join(tmpdir, "test.db")
        os.environ["NDJSON_PATH"] = os.path.join(tmpdir, "events.ndjson")
        os.environ["PATTERN_PACK_DIR"] = os.path.join(tmpdir, "packs")
        
        # Create packs directory
        packs_dir = os.path.join(tmpdir, "packs")
        os.makedirs(packs_dir)
        
        # Create valid pattern pack
        pack_data = {
            "schema": "pattern_pack_v1",
            "pack_id": "test_pack_001",
            "built_at": datetime.now(timezone.utc).isoformat(),
            "hash": "abc123",
            "symbols": ["BTCUSDT"],
            "timeframes": ["15m", "1h", "4h"],
            "patterns_by_symbol": {},
        }
        
        pack_path = os.path.join(packs_dir, "pattern_pack_v1.json")
        with open(pack_path, "w") as f:
            json.dump(pack_data, f)
        
        from tezaver.bulut.core.context import bootstrap_context
        from tezaver.bulut.core.config import reload_config
        
        reload_config()
        ctx = bootstrap_context()
        
        # Load pattern pack
        result = ctx.load_pattern_pack()
        
        assert result is True
        assert ctx.state.pattern_pack_loaded is True
        assert ctx.state.pattern_pack_id == "test_pack_001"
        
        # Trade should be unlocked (assuming no positions)
        ctx.update_trade_lock()
        assert ctx.state.trade_locked is False
