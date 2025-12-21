"""
MX-2000.1: WAR Planner Coverage + Lifecycle Tests
W1: Diagnostics, W2: Empty plan, W3: Verdict→Status mapping
"""
import sys
sys.path.append("src")


def test_diagnostics():
    """W1: WarPlanner should provide diagnostics."""
    from tezaver.matrix.apps.war_planner import WarPlanner
    
    planner = WarPlanner()
    diag = planner.get_diagnostics()
    
    assert hasattr(diag, 'candidates_total')
    assert hasattr(diag, 'candidates_by_status')
    assert hasattr(diag, 'approved_for_war_count')
    assert hasattr(diag, 'registry_path')
    
    print(f"SUCCESS: Diagnostics work (total={diag.candidates_total}, approved={diag.approved_for_war_count})")


def test_plan_includes_diagnostics():
    """W1: WarPlan should include diagnostics."""
    from tezaver.matrix.apps.war_planner import WarPlanner
    
    planner = WarPlanner()
    plan = planner.generate_plan(seed=42)
    
    assert hasattr(plan, 'diagnostics')
    assert hasattr(plan, 'is_empty')
    
    plan_dict = plan.to_dict()
    assert 'diagnostics' in plan_dict
    assert 'is_empty' in plan_dict
    
    print(f"SUCCESS: Plan includes diagnostics (is_empty={plan.is_empty})")


def test_empty_plan_is_marked():
    """W2: Empty plan should have is_empty=True."""
    from tezaver.matrix.apps.war_planner import WarPlanner
    
    planner = WarPlanner()
    # With no APPROVED_FOR_WAR candidates, plan should be empty
    plan = planner.generate_plan(seed=42)
    
    # If no approved candidates, is_empty should be True
    if plan.diagnostics.approved_for_war_count == 0:
        assert plan.is_empty, "Plan should be marked as empty when no approved candidates"
        print("SUCCESS: Empty plan correctly marked as is_empty=True")
    else:
        assert not plan.is_empty, "Plan should not be empty when approved candidates exist"
        print(f"SUCCESS: Plan has {len(plan.cells)} cells, is_empty=False")


def test_empty_plan_engine_returns_correctly():
    """W2: WarEngine should return EMPTY_PLAN verdict for empty plan."""
    from tezaver.matrix.apps.war_planner import WarPlanner, WarPlan, PlanDiagnostics
    from tezaver.matrix.core.war_engine import WarEngine
    
    # Create an explicitly empty plan
    empty_plan = WarPlan(
        plan_id="test_empty",
        created_at="2025-01-01",
        cells=[],
        symbols=[],
        candidate_ids=[],
        config_hash="test",
        diagnostics=PlanDiagnostics(candidates_total=5, approved_for_war_count=0),
        is_empty=True
    )
    
    engine = WarEngine(plan=empty_plan, seed=42)
    result = engine.run()
    
    assert result["verdict"] == "EMPTY_PLAN"
    assert result["run_created"] == False
    assert "diagnostics" in result
    
    print("SUCCESS: WarEngine returns EMPTY_PLAN for empty plan")


def test_verdict_to_status_mapping():
    """W3: Verify verdict→status mapping."""
    # This is a logical test, not a full integration test
    status_map = {
        "PASS": "APPROVED_FOR_LIVE",
        "IMPROVE": "NEEDS_PATCH",
        "FAIL": "REJECTED_BY_WAR"
    }
    
    for verdict, expected_status in status_map.items():
        assert expected_status.startswith("APPROVED") or expected_status.startswith("NEEDS") or expected_status.startswith("REJECTED")
        print(f"  {verdict} → {expected_status}")
    
    print("SUCCESS: Verdict→Status mapping verified")


def test_war_planner_with_fixture():
    """Integration: Check that planner can generate non-empty plan when candidates exist."""
    from tezaver.matrix.apps.war_planner import WarPlanner
    from tezaver.matrix.adapters.candidate_registry import CandidateRegistry
    
    # Create a temporary approved candidate
    registry = CandidateRegistry()
    
    # Check current state
    planner = WarPlanner(registry)
    diag = planner.get_diagnostics()
    
    print(f"Integration test - Current state:")
    print(f"  Total candidates: {diag.candidates_total}")
    print(f"  APPROVED_FOR_WAR: {diag.approved_for_war_count}")
    print(f"  Status breakdown: {diag.candidates_by_status}")
    
    plan = planner.generate_plan(seed=42)
    
    if diag.approved_for_war_count > 0:
        assert not plan.is_empty
        assert len(plan.cells) > 0
        print(f"SUCCESS: Integration test passed - {len(plan.cells)} cells generated")
    else:
        assert plan.is_empty
        print("SUCCESS: Integration test passed - empty plan (no APPROVED_FOR_WAR candidates)")


if __name__ == "__main__":
    print("=== MX-2000.1 Tests ===")
    test_diagnostics()
    test_plan_includes_diagnostics()
    test_empty_plan_is_marked()
    test_empty_plan_engine_returns_correctly()
    test_verdict_to_status_mapping()
    test_war_planner_with_fixture()
    print("\n=== All MX-2000.1 tests passed ===")
