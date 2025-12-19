# Tezaver Bulut - Recovery API Tests (P10)
"""
Tests for Recovery REST endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch

from tezaver.bulut.app_backend import app
from tezaver.bulut.core.context import BulutContext


@pytest.fixture
def app_client():
    """Create test client with OpsAuth bypassed and mocked context."""
    
    async def noop_auth(request, config):
        pass
    
    with patch("tezaver.bulut.app_backend.check_ops_auth", noop_auth):
        with patch("tezaver.bulut.app_backend.bootstrap_context") as mock_bootstrap:
            ctx = MagicMock(spec=BulutContext)
            
            # Basic config
            ctx.config.mode = "REAL_MAINNET"
            ctx.config.time_sync_enabled = False
            ctx.config.exchangeinfo_refresh_on_start = False
            ctx.config.startup_selftest_enabled = False
            ctx.config.proof_ladder_auto_evaluate_enabled = False
            ctx.config.user_data_ws_enabled = False
            ctx.config.migrations_enabled = False
            ctx.config.dry_run_enabled = False
            ctx.config.ops_auth_enabled = False
            
            # State
            ctx.state.pattern_pack_loaded = True
            ctx.state.trade_locked = False
            
            # Mock dependencies
            ctx.persistence = MagicMock()
            ctx.persistence.get_positions.return_value = []
            ctx.telemetry = MagicMock()
            ctx.scheduler = MagicMock()
            ctx.scheduler.start = AsyncMock()
            ctx.scheduler.stop = AsyncMock()
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
            
            # Restart Recovery
            ctx.restart_recovery = MagicMock()
            ctx.restart_recovery.get_status.return_value = {
                "status": "PASS",
                "last_run_ts": "2024-01-01T00:00:00Z",
                "run_id": "test_run",
                "mode": "REAL_MAINNET",
                "blockers": [],
                "stats": {},
                "is_stale": False,
                "can_resume": True,
                "resume_blockers": []
            }
            ctx.restart_recovery.can_resume.return_value = (True, [])
            ctx.restart_recovery.safe_boot.return_value = (True, "Safe boot")
            
            # Mock run to return a report-like object
            run_result = MagicMock()
            run_result.status = MagicMock()
            run_result.status.value = "PASS"
            run_result.blockers = []
            run_result.stats = {}
            run_result.duration_ms = 100
            ctx.restart_recovery.run.return_value = run_result

            mock_bootstrap.return_value = ctx

            client = TestClient(app, base_url="http://localhost:8000")
            
            yield client, ctx


def test_get_recovery_status(app_client):
    """Test GET /recovery/status returns expected shape."""
    client, ctx = app_client
    
    with client:
        res = client.get("/recovery/status")
        
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "can_resume" in data


def test_run_recovery(app_client):
    """Test POST /recovery/run triggers recovery."""
    client, ctx = app_client
    
    with client:
        res = client.post("/recovery/run", json={"force": False})
        
        assert res.status_code == 200
        assert res.json()["success"] == True


def test_can_resume(app_client):
    """Test GET /recovery/can_resume returns eligibility."""
    client, ctx = app_client
    
    with client:
        res = client.get("/recovery/can_resume")
        
        assert res.status_code == 200
        data = res.json()
        assert "can_resume" in data


def test_safe_boot(app_client):
    """Test POST /recovery/safe_boot triggers safe boot."""
    client, ctx = app_client
    
    with client:
        res = client.post("/recovery/safe_boot")
        
        assert res.status_code == 200
        assert res.json()["success"] == True
