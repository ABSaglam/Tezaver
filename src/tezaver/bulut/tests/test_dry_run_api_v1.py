# Tezaver Bulut - Dry Run API Tests (P4)
"""
Tests for Dry-Run API endpoints.
Patches check_ops_auth to bypass OpsAuth middleware completely.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch

from tezaver.bulut.app_backend import app
from tezaver.bulut.core.context import BulutContext


@pytest.fixture
def app_client():
    """Create test client with OpsAuth bypassed and mocked context."""
    
    # Patch check_ops_auth to be a no-op (bypasses OpsAuth completely)
    async def noop_auth(request, config):
        pass
    
    with patch("tezaver.bulut.app_backend.check_ops_auth", noop_auth):
        with patch("tezaver.bulut.app_backend.bootstrap_context") as mock_bootstrap:
            ctx = MagicMock(spec=BulutContext)
            
            # Setup basic state for startup
            ctx.state.pattern_pack_loaded = True
            ctx.state.trade_locked = False
            ctx.config.mode = "SANDBOX"
            ctx.config.time_sync_enabled = False
            ctx.config.exchangeinfo_refresh_on_start = False
            ctx.config.startup_selftest_enabled = False
            ctx.config.proof_ladder_auto_evaluate_enabled = False
            ctx.config.user_data_ws_enabled = False
            ctx.config.migrations_enabled = False
            ctx.config.dry_run_enabled = True
            ctx.config.ops_auth_enabled = False
            
            # Mock dependencies
            ctx.persistence = MagicMock()
            ctx.telemetry = MagicMock()
            ctx.universe_source = MagicMock()
            ctx.bars_store = MagicMock()
            
            # Scheduler
            ctx.scheduler = MagicMock()
            ctx.scheduler.start = AsyncMock()
            ctx.scheduler.stop = AsyncMock()
            
            # Dry Run Service
            ctx.dry_run_service = MagicMock()
            ctx.dry_run_service.start_run = AsyncMock(return_value="DRY_TEST_123")
            ctx.dry_run_service.get_status.return_value = {"running": False}
            
            # Mock Lifespan dependencies
            ctx.time_sync = MagicMock()
            ctx.time_sync.refresh = AsyncMock()
            ctx.exchangeinfo_cache = MagicMock()
            ctx.exchangeinfo_cache.refresh = AsyncMock()
            ctx.task_supervisor = MagicMock()
            ctx.task_supervisor.start_all = AsyncMock()
            ctx.task_supervisor.stop_all = AsyncMock()
            ctx.reconciliation_service = MagicMock()
            ctx.reconciliation_service.reconcile = AsyncMock(return_value={"status": "OK"})
            ctx.executor = MagicMock()
            ctx.executor.recover_executing_plans = AsyncMock()
            ctx.constitution_guard = MagicMock()
            ctx.migration_runner = MagicMock()

            mock_bootstrap.return_value = ctx

            client = TestClient(app, base_url="http://localhost:8000")
            
            yield client, ctx


def test_start_dry_run(app_client):
    """Test POST /dry_run/start returns 200 and run_id."""
    client, ctx = app_client
    
    with client:
        res = client.post("/dry_run/start", json={"cycles": 10})
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        assert res.json()["run_id"] == "DRY_TEST_123"
        
        ctx.dry_run_service.start_run.assert_called_with(10)


def test_get_status(app_client):
    """Test GET /dry_run/status returns running state."""
    client, ctx = app_client
    
    with client:
        res = client.get("/dry_run/status")
        assert res.status_code == 200
        assert res.json()["running"] == False


def test_get_runs(app_client):
    """Test GET /dry_run/runs/latest returns run history."""
    client, ctx = app_client
    
    ctx.persistence.get_latest_dry_runs.return_value = [
        {"run_id": "r1", "status": "SUCCESS", "summary": {}}
    ]
    
    with client:
        res = client.get("/dry_run/runs/latest")
        assert res.status_code == 200
        assert len(res.json()) == 1
        assert res.json()[0]["run_id"] == "r1"
