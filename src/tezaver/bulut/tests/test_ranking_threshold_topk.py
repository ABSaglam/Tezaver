# Tezaver Bulut - Ranking Threshold/TopK Tests
"""
Tests for threshold and topk filtering in ranking.
"""

import pytest
from datetime import datetime, timezone


def test_shortlist_empty_when_all_below_threshold():
    """Shortlist should be empty when all candidates are below threshold."""
    from tezaver.bulut.schemas.ranking_snapshot_v1 import (
        RankingSnapshotV1,
        CandidateScore,
    )
    
    ranking = RankingSnapshotV1(
        cycle_ts=datetime.now(timezone.utc),
        base_tf="15m",
        derived_tfs=["1h", "4h"],
        universe_size=3,
        threshold=70,  # High threshold
        topk=20,
        candidates=[
            CandidateScore(symbol="BTCUSDT", score=50.0, components={}, flags=[]),
            CandidateScore(symbol="ETHUSDT", score=60.0, components={}, flags=[]),
            CandidateScore(symbol="SOLUSDT", score=65.0, components={}, flags=[]),
        ],
    )
    
    shortlist = ranking.shortlist
    
    assert len(shortlist) == 0, "Shortlist should be empty when all below threshold"


def test_shortlist_respects_threshold():
    """Shortlist should only include candidates above threshold."""
    from tezaver.bulut.schemas.ranking_snapshot_v1 import (
        RankingSnapshotV1,
        CandidateScore,
    )
    
    ranking = RankingSnapshotV1(
        cycle_ts=datetime.now(timezone.utc),
        base_tf="15m",
        derived_tfs=["1h", "4h"],
        universe_size=5,
        threshold=70,
        topk=20,
        candidates=[
            CandidateScore(symbol="BTCUSDT", score=85.0, components={}, flags=[]),
            CandidateScore(symbol="ETHUSDT", score=75.0, components={}, flags=[]),
            CandidateScore(symbol="SOLUSDT", score=65.0, components={}, flags=[]),
            CandidateScore(symbol="XRPUSDT", score=70.0, components={}, flags=[]),  # Exactly at threshold
            CandidateScore(symbol="ADAUSDT", score=69.9, components={}, flags=[]),
        ],
    )
    
    shortlist = ranking.shortlist
    symbols = [c.symbol for c in shortlist]
    
    assert len(shortlist) == 3
    assert "BTCUSDT" in symbols
    assert "ETHUSDT" in symbols
    assert "XRPUSDT" in symbols  # Exactly at threshold should be included
    assert "SOLUSDT" not in symbols
    assert "ADAUSDT" not in symbols


def test_shortlist_respects_topk_limit():
    """Shortlist should be limited to topk candidates."""
    from tezaver.bulut.schemas.ranking_snapshot_v1 import (
        RankingSnapshotV1,
        CandidateScore,
    )
    
    # Create 10 candidates all above threshold
    candidates = [
        CandidateScore(symbol=f"SYM{i}USDT", score=90.0 - i, components={}, flags=[])
        for i in range(10)
    ]
    
    ranking = RankingSnapshotV1(
        cycle_ts=datetime.now(timezone.utc),
        base_tf="15m",
        derived_tfs=["1h", "4h"],
        universe_size=10,
        threshold=70,
        topk=3,  # Only top 3
        candidates=candidates,
    )
    
    shortlist = ranking.shortlist
    
    assert len(shortlist) == 3
    assert shortlist[0].symbol == "SYM0USDT"  # Highest score
    assert shortlist[1].symbol == "SYM1USDT"
    assert shortlist[2].symbol == "SYM2USDT"


def test_shortlist_sorted_by_score():
    """Shortlist should be sorted by score descending."""
    from tezaver.bulut.schemas.ranking_snapshot_v1 import (
        RankingSnapshotV1,
        CandidateScore,
    )
    
    ranking = RankingSnapshotV1(
        cycle_ts=datetime.now(timezone.utc),
        base_tf="15m",
        derived_tfs=["1h", "4h"],
        universe_size=3,
        threshold=70,
        topk=20,
        candidates=[
            CandidateScore(symbol="SOLUSDT", score=75.0, components={}, flags=[]),
            CandidateScore(symbol="BTCUSDT", score=90.0, components={}, flags=[]),
            CandidateScore(symbol="ETHUSDT", score=85.0, components={}, flags=[]),
        ],
    )
    
    shortlist = ranking.shortlist
    
    assert shortlist[0].symbol == "BTCUSDT"  # 90
    assert shortlist[1].symbol == "ETHUSDT"  # 85
    assert shortlist[2].symbol == "SOLUSDT"  # 75


def test_scanner_produces_ranking_without_pattern_pack():
    """Scanner should produce ranking even without pattern pack."""
    from tezaver.bulut.core.config import BulutConfig
    from tezaver.bulut.engine.scanner import Scanner
    
    config = BulutConfig()
    scanner = Scanner(config, pattern_pack=None)
    
    # Set small universe for test
    scanner.set_symbols(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    
    ranking = scanner.scan()
    
    assert ranking is not None
    assert ranking.universe_size == 3
    assert len(ranking.candidates) == 3
    
    # Pattern component should be 0 without pack
    for candidate in ranking.candidates:
        assert candidate.components.get("pattern", -1) == 0
