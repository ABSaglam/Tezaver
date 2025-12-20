import pytest
from fastapi.testclient import TestClient
# Assuming we can grab the main app or router from somewhere
# For smoke test, we'll try to init the simplest app possible or mock
# Since we updated routes_runbook.py, we really want to check if that compiles/runs.

from tezaver.bulut.api.routes_runbook import router as runbook_router
from fastapi import FastAPI

def test_runbook_snapshot_schema_smoke():
    """
    Smoke test to ensure the Runbook snapshot Endpoint works (or at least builds).
    We may not have the full Context active, so we expect potential 500s or handled errors,
    but we want to ensure the code path for 'perf_cost' doesn't crash the interpreter.
    """
    app = FastAPI()
    app.include_router(runbook_router)
    client = TestClient(app)
    
    # We need to inject a mock context into app.state.context
    class MockContext:
        class MockConfig:
            mode = "TEST"
        class MockPerf:
            current_mode = "TEST_MODE"
            budget_usage_pct = 12.5
            last_cycle_ms = 450
            def get_recommendations(self): return []
        
        config = MockConfig()
        state = {}
        perf_manager = MockPerf()
        # Add other mocks to prevent AttributeError if possible, or rely on try/except blocks in code
        constitution_guard = None
        drift_guard = None
        time_sync = None
        exchangeinfo_cache = None
        launch_checklist = None
        proof_ladder = None
        pilot_meter = None
        expansion_policy = None
        autopilot_service = None
        allocation_engine = None
        exit_intel_engine = None
        kill_switch = None
        restart_recovery = None
        class MockPersistence:
             def get_recent_cycles(self, limit=5): return []
        persistence = MockPersistence()

    app.state.context = MockContext()

    # Act
    res = client.get("/runbook/snapshot")
    
    # Assert
    assert res.status_code == 200
    data = res.json()
    assert "perf_cost" in data
    assert data["perf_cost"]["mode"] == "TEST_MODE"
    assert data["perf_cost"]["cycle_ms"] == 450
