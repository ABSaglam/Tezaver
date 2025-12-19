# Tezaver Bulut - Kill Switch API Tests (P9)
"""
Tests for Kill Switch REST endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch

from tezaver.bulut.app_backend import app
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.core.kill_switch import KillSwitchState


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
            
            # Kill Switch
            ctx.kill_switch = MagicMock()
            ctx.kill_switch.get_status.return_value = {
                "state": "NORMAL",
                "reason": None,
                "actor": None,
                "changed_at": None,
                "entries_allowed": True,
                "autopilot_allowed": True,
                "is_halted": False,
                "events_count": 0
            }
            ctx.kill_switch.halt.return_value = (True, "Halted successfully")
            ctx.kill_switch.safe.return_value = (True, "Safe mode activated")
            ctx.kill_switch.flatten.return_value = (True, "Flatten initiated", [])
            ctx.kill_switch.resume.return_value = (True, "Resumed")
            ctx.kill_switch.get_events.return_value = []

            mock_bootstrap.return_value = ctx

            client = TestClient(app, base_url="http://localhost:8000")
            
            yield client, ctx


def test_get_kill_switch_status(app_client):
    """Test GET /kill_switch/status returns expected shape."""
    client, ctx = app_client
    
    with client:
        res = client.get("/kill_switch/status")
        
        assert res.status_code == 200
        data = res.json()
        assert "state" in data
        assert "entries_allowed" in data


def test_halt(app_client):
    """Test POST /kill_switch/halt triggers halt."""
    client, ctx = app_client
    
    with client:
        res = client.post("/kill_switch/halt", json={
            "reason": "test halt",
            "actor": "test_user"
        })
        
        assert res.status_code == 200
        assert res.json()["success"] == True
        ctx.kill_switch.halt.assert_called()


def test_safe_mode(app_client):
    """Test POST /kill_switch/safe triggers safe mode."""
    client, ctx = app_client
    
    with client:
        res = client.post("/kill_switch/safe", json={
            "reason": "test safe"
        })
        
        assert res.status_code == 200
        assert res.json()["success"] == True


def test_flatten(app_client):
    """Test POST /kill_switch/flatten triggers flatten."""
    client, ctx = app_client
    
    with client:
        res = client.post("/kill_switch/flatten", json={
            "reason": "test flatten"
        })
        
        assert res.status_code == 200
        assert res.json()["success"] == True


def test_resume(app_client):
    """Test POST /kill_switch/resume returns to normal."""
    client, ctx = app_client
    
    with client:
        res = client.post("/kill_switch/resume", json={
            "reason": "test resume"
        })
        
        assert res.status_code == 200
        assert res.json()["success"] == True
