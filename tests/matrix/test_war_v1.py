"""
MX-2000: WAR v1 Unit Tests
Tests for RiskLimiter, WarScorecard, WarJudge, and integration.
"""
import sys
sys.path.append("src")


def test_risk_limiter_block():
    """RiskLimiter should block when limits exceeded."""
    from tezaver.matrix.core.risk_limiter import RiskLimiter, RiskLimits
    
    limiter = RiskLimiter(RiskLimits(
        max_total_notional=10000,
        max_concurrent_positions=2,
        max_notional_per_symbol=5000
    ))
    
    # First position OK
    allowed, reason = limiter.check_order("BTCUSDT", 3000, "cand1", 1)
    assert allowed, f"First order should be allowed, got: {reason}"
    limiter.open_position("BTCUSDT", 3000, "cand1", 1)
    
    # Second position OK
    allowed, reason = limiter.check_order("ETHUSDT", 3000, "cand2", 2)
    assert allowed, f"Second order should be allowed, got: {reason}"
    limiter.open_position("ETHUSDT", 3000, "cand2", 2)
    
    # Third position BLOCKED (max concurrent)
    allowed, reason = limiter.check_order("SOLUSDT", 2000, "cand3", 3)
    assert not allowed, "Third order should be blocked (max concurrent)"
    assert "MAX_CONCURRENT_POSITIONS" in reason
    
    print("SUCCESS: RiskLimiter block logic works")


def test_risk_limiter_notional_per_symbol():
    """RiskLimiter should block when symbol notional exceeded."""
    from tezaver.matrix.core.risk_limiter import RiskLimiter, RiskLimits
    
    limiter = RiskLimiter(RiskLimits(
        max_total_notional=100000,
        max_concurrent_positions=10,
        max_notional_per_symbol=5000
    ))
    
    limiter.open_position("BTCUSDT", 4000, "cand1", 1)
    
    # Additional order on same symbol exceeds limit
    allowed, reason = limiter.check_order("BTCUSDT", 2000, "cand2", 2)
    assert not allowed, "Should be blocked (max notional per symbol)"
    assert "MAX_NOTIONAL_PER_SYMBOL" in reason
    
    print("SUCCESS: RiskLimiter per-symbol limit works")


def test_war_scorecard():
    """WarScorecard should calculate metrics correctly."""
    from tezaver.matrix.core.war_scorecard import WarScorecard
    
    scorecard = WarScorecard()
    
    scorecard.record_trade("cand1", "BTCUSDT", 100.0, 1.0, 0.5, True)
    scorecard.record_trade("cand1", "BTCUSDT", -50.0, 1.0, 0.5, False)
    scorecard.record_trade("cand2", "ETHUSDT", 75.0, 0.5, 0.25, True)
    scorecard.record_risk_block()
    
    scorecard.finalize()
    result = scorecard.to_dict()
    
    assert result["total_trades"] == 3
    assert result["net_pnl"] == 125.0  # 100 - 50 + 75
    assert result["fee_cost_total"] == 2.5  # 1 + 1 + 0.5
    assert result["risk_blocks_count"] == 1
    assert len(result["by_candidate"]) == 2
    assert len(result["by_symbol"]) == 2
    assert result["scorecard_hash"]  # Should have a hash
    
    print(f"SUCCESS: WarScorecard calculates correctly (hash={result['scorecard_hash']})")


def test_war_judge_verdict():
    """WarJudge should produce correct verdicts."""
    from tezaver.matrix.core.war_judge import WarJudge, WarGates
    
    judge = WarJudge(WarGates(
        min_total_trades=10,
        max_drawdown_pct=20.0,
        min_profitable_pnl=0.0
    ))
    
    # PASS case
    scorecard_pass = {
        "total_trades": 15,
        "max_drawdown": 10.0,
        "net_pnl": 100.0,
        "risk_blocks_count": 0
    }
    verdict, reasons = judge.evaluate(scorecard_pass)
    assert verdict == "PASS", f"Expected PASS, got {verdict}"
    
    # FAIL case (low trades)
    scorecard_fail = {
        "total_trades": 5,
        "max_drawdown": 25.0,  # Also exceeds drawdown
        "net_pnl": -50.0,
        "risk_blocks_count": 3
    }
    verdict, reasons = judge.evaluate(scorecard_fail)
    assert verdict == "FAIL", f"Expected FAIL, got {verdict}"
    
    print("SUCCESS: WarJudge produces correct verdicts")


def test_war_planner():
    """WarPlanner should generate plan from approved candidates."""
    from tezaver.matrix.apps.war_planner import WarPlanner
    
    planner = WarPlanner()
    plan = planner.generate_plan(max_candidates=5, seed=42)
    
    # Plan should be generated (may be empty if no APPROVED_FOR_WAR candidates)
    assert plan.plan_id.startswith("war_")
    assert plan.config_hash
    
    print(f"SUCCESS: WarPlanner generates plan (cells={len(plan.cells)})")


def test_determinism():
    """Same inputs should produce same scorecard hash."""
    from tezaver.matrix.core.war_scorecard import WarScorecard
    
    def make_scorecard():
        sc = WarScorecard()
        sc.record_trade("cand1", "BTCUSDT", 100.0, 1.0, 0.5, True)
        sc.record_trade("cand2", "ETHUSDT", 50.0, 0.5, 0.25, True)
        sc.finalize()
        return sc.get_hash()
    
    hash1 = make_scorecard()
    hash2 = make_scorecard()
    
    assert hash1 == hash2, f"Hashes should match: {hash1} != {hash2}"
    
    print(f"SUCCESS: Determinism verified (hash={hash1})")


if __name__ == "__main__":
    print("=== MX-2000 WAR v1 Tests ===")
    test_risk_limiter_block()
    test_risk_limiter_notional_per_symbol()
    test_war_scorecard()
    test_war_judge_verdict()
    test_war_planner()
    test_determinism()
    print("\n=== All MX-2000 tests passed ===")
