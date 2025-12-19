# Tezaver Bulut - Pattern v2 Tests
import pytest
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from tezaver.bulut.services.pattern_pack_loader import PatternPackLoader
from tezaver.bulut.engine.scanner import Scanner
from tezaver.bulut.engine.decider import Decider
from tezaver.bulut.schemas.ranking_snapshot_v1 import RankingSnapshotV1
from tezaver.bulut.schemas.trade_plan_v1 import TradeDecision
from tezaver.bulut.core.config import BulutConfig

@pytest.fixture
def v2_pack_file(tmp_path):
    """Create a v2 pattern pack file."""
    pack_data = {
        "schema": "pattern_pack_v1",
        "pack_id": "TEST_PACK_V2",
        "built_at": datetime.now().isoformat(),
        "hash": "test_hash",
        "symbols": ["BTCUSDT"],
        "timeframes": ["15m"],
        "patterns_by_symbol": {
            "BTCUSDT": [
                {
                    "pattern_id": "SILVER_BULL",
                    "tf": "15m", 
                    "kind": "ENTRY",
                    "confidence": 0.95,
                    "evidence": {"note": "Strong buy"}
                },
                {
                    "pattern_id": "RALLY_START",
                    "tf": "15m", 
                    "kind": "EVENT",
                    "confidence": 0.85,
                    "evidence": {"note": "Volume spike"}
                }
            ]
        }
    }
    p = tmp_path / "test_pack_v2.json"
    p.write_text(json.dumps(pack_data))
    return p

def test_loader_deterministic_match(tmp_path, v2_pack_file):
    """Verify loading and scoring logic."""
    loader = PatternPackLoader(str(tmp_path))
    loader.check_reload()
    
    # 1. Match Structure
    match = loader.match_symbol("BTCUSDT", topn=2)
    assert len(match["matches"]) == 2
    assert match["matches"][0]["pattern_id"] == "SILVER_BULL"
    assert match["matches"][0]["confidence"] == 0.95
    assert match["matches"][1]["pattern_id"] == "RALLY_START"
    
    # 2. Score Calculation (Avg of top 2)
    # (0.95 + 0.85) / 2 = 0.90 -> 90.0 score
    assert abs(match["score"] - 90.0) < 0.01

def test_scanner_populates_matches(tmp_path, v2_pack_file):
    """Verify scanner populates matched_patterns."""
    loader = PatternPackLoader(str(tmp_path))
    loader.check_reload()
    
    # Initialize with low threshold to pass filters
    config = BulutConfig(scan_min_score=0, trade_min_score=0)
    scanner = Scanner(config, pattern_loader=loader, universe=["BTCUSDT"])
    
    snapshot = scanner.scan()
    assert len(snapshot.candidates) > 0 # Ensure we have candidates
    cand = snapshot.candidates[0]
    
    assert cand.symbol == "BTCUSDT"
    assert len(cand.matched_patterns) == 2
    assert cand.matched_patterns[0]["pattern_id"] == "SILVER_BULL"
    # Score should be match["score"] * 0.6 = 90 * 0.6 = 54.0
    assert abs(cand.components["pattern"] - 54.0) < 0.1

def test_decider_propagates_to_plan(tmp_path, v2_pack_file):
    """Verify decider puts pattern info into reasons."""
    loader = PatternPackLoader(str(tmp_path))
    loader.check_reload()
    
    # Run scan to get candidate with matches
    config = BulutConfig(scan_min_score=0, trade_min_score=0)
    scanner = Scanner(config, pattern_loader=loader, universe=["BTCUSDT"])
    snapshot = scanner.scan()
    
    # Create mock ctx for Decider (v0.22 API)
    ctx = MagicMock()
    ctx.config = config
    ctx.policy = MagicMock()
    ctx.entry_sizing_resolver = MagicMock()
    ctx.entry_sizing_resolver.resolve.return_value = MagicMock(
        blocked=False,
        notional_usdt=100,
        profile_id="test",
        explain="test",
        leverage=None,
        block_reason=None
    )
    
    # Run Decider
    decider = Decider(ctx)
    plans = decider.decide(snapshot, 0, 0.0, True, allowlist=None)
    
    assert len(plans) == 1
    plan = plans[0]
    assert plan.decision == TradeDecision.OPEN
    
    # Check Reasons
    reasons = plan.reasons
    assert reasons["pattern_id"] == "SILVER_BULL"
    assert reasons["pattern_confidence"] == 0.95
    assert reasons["pattern_note"] == "Strong buy"
