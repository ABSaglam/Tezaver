# Tezaver Bulut - Ranking Stabilizer Tests
"""
Tests for RankingStabilizer logic.
"""

from datetime import datetime, timedelta, timezone
from tezaver.bulut.schemas.ranking_snapshot_v1 import CandidateScore
from tezaver.bulut.services.ranking_stabilizer import RankingStabilizer

def test_stabilize_bonus():
    """Previous TopK item should get bonus."""
    stabilizer = RankingStabilizer()
    ts1 = datetime.now(timezone.utc)
    
    # Cycle 1: A=80, B=75. TopK=1.
    cands1 = [
        CandidateScore("A", 80.0, {}, []),
        CandidateScore("B", 75.0, {}, [])
    ]
    res1 = stabilizer.stabilize(ts1, cands1, topk=1, threshold=70, bonus=10.0)
    assert len(res1) == 1
    assert res1[0].symbol == "A"
    
    # Cycle 2: A drops to 72, B stays 75.
    # Without bonus, B would win.
    # With bonus (A was TopK), A becomes 82.
    ts2 = ts1 + timedelta(minutes=15)
    cands2 = [
        CandidateScore("A", 72.0, {}, []),
        CandidateScore("B", 75.0, {}, [])
    ]
    res2 = stabilizer.stabilize(ts2, cands2, topk=1, threshold=70, bonus=10.0)
    
    assert len(res2) == 1
    assert res2[0].symbol == "A" # A wins due to bonus
    assert res2[0].score == 82.0 
    assert "STABLE_BONUS" in res2[0].flags

def test_stabilize_threshold_filter():
    """Items below threshold should be filtered even if they have history."""
    stabilizer = RankingStabilizer()
    ts = datetime.now(timezone.utc)
    
    # A was previously TopK (inject history)
    stabilizer._history["A"] = ts
    
    # A drops way below threshold
    cands = [CandidateScore("A", 50.0, {}, [])]
    
    # Even with bonus (50+10=60) it is < 70 threshold
    res = stabilizer.stabilize(ts, cands, topk=1, threshold=70, bonus=10.0)
    
    assert len(res) == 0
