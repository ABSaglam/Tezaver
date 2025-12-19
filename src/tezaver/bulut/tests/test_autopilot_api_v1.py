# Tezaver Bulut - Autopilot API Tests (P5)
"""
Tests for Autopilot REST endpoints.
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
            
            # Autopilot Service
            ctx.autopilot_service = MagicMock()
            ctx.autopilot_service.get_status.return_value = {
                "enabled": False,
                "can_operate": True,
                "block_reason": None,
                "last_block_reason": None,
                "max_entries_per_cycle": 1
            }
            ctx.autopilot_service.enable.return_value = True
            ctx.autopilot_service.disable = MagicMock()
            
            # Pilot Meter
            ctx.pilot_meter = MagicMock()
            ctx.pilot_meter.get_status.return_value = {
                "active": False,
                "start_ts": None,
                "end_ts": None,
                "limit_usdt": 50.0,
                "committed_usdt": 0.0,
                "remaining_usdt": 50.0,
                "time_left_hours": 24.0
            }

            mock_bootstrap.return_value = ctx

            client = TestClient(app, base_url="http://localhost:8000")
            
            yield client, ctx


def test_get_autopilot_status(app_client):
    """Test GET /autopilot/status returns expected shape."""
    client, ctx = app_client
    
    with client:
        res = client.get("/autopilot/status")
        
        assert res.status_code == 200
        data = res.json()
        assert "enabled" in data
        assert "can_operate" in data
        assert "block_reason" in data


def test_enable_autopilot_success(app_client):
    """Test POST /autopilot/enable with enabled=true."""
    client, ctx = app_client
    
    with client:
        res = client.post("/autopilot/enable", json={"enabled": True})
        
        assert res.status_code == 200
        assert res.json()["enabled"] == True
        ctx.autopilot_service.enable.assert_called()


def test_disable_autopilot(app_client):
    """Test POST /autopilot/enable with enabled=false."""
    client, ctx = app_client
    
    with client:
        res = client.post("/autopilot/enable", json={"enabled": False})
        
        assert res.status_code == 200
        assert res.json()["enabled"] == False
        ctx.autopilot_service.disable.assert_called()


def test_get_pilot_status(app_client):
    """Test GET /autopilot/pilot/status returns expected shape."""
    client, ctx = app_client
    
    with client:
        res = client.get("/autopilot/pilot/status")
        
        assert res.status_code == 200
        data = res.json()
        assert "limit_usdt" in data
        assert "committed_usdt" in data
        assert "remaining_usdt" in data
        assert data["limit_usdt"] == 50.0
