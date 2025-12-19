# Tezaver Bulut - Expansion API Tests (P6)
"""
Tests for Expansion REST endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch

from tezaver.bulut.app_backend import app
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.core.expansion_policy import ExpansionTier


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
            ctx.config.expansion_enabled = True
            
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
            
            # Expansion Policy
            ctx.expansion_policy = MagicMock()
            ctx.expansion_policy.get_status.return_value = {
                "enabled": True,
                "current_tier": 0,
                "current_tier_name": "T0_PILOT",
                "limit_usdt": 50.0,
                "max_tier": 2,
                "can_step_up": True,
                "block_reasons": [],
                "tier_changed_ts": None,
                "tier_history": []
            }
            ctx.expansion_policy.step_up.return_value = (True, None)
            ctx.expansion_policy.set_tier.return_value = (True, None)
            ctx.expansion_policy.get_current_tier.return_value = ExpansionTier.T0_PILOT
            ctx.expansion_policy.get_tier_limit.return_value = 50.0

            mock_bootstrap.return_value = ctx

            client = TestClient(app, base_url="http://localhost:8000")
            
            yield client, ctx


def test_get_expansion_status(app_client):
    """Test GET /expansion/status returns expected shape."""
    client, ctx = app_client
    
    with client:
        res = client.get("/expansion/status")
        
        assert res.status_code == 200
        data = res.json()
        assert "current_tier" in data
        assert "limit_usdt" in data
        assert "can_step_up" in data


def test_step_up_success(app_client):
    """Test POST /expansion/step_up succeeds."""
    client, ctx = app_client
    
    with client:
        res = client.post("/expansion/step_up")
        
        assert res.status_code == 200
        assert res.json()["success"] == True
        ctx.expansion_policy.step_up.assert_called()


def test_step_up_blocked(app_client):
    """Test POST /expansion/step_up returns 409 when blocked."""
    client, ctx = app_client
    ctx.expansion_policy.step_up.return_value = (False, "Blocked: proof_ladder_insufficient")
    
    with client:
        res = client.post("/expansion/step_up")
        
        assert res.status_code == 409


def test_set_tier(app_client):
    """Test POST /expansion/set_tier sets tier forcefully."""
    client, ctx = app_client
    
    with client:
        res = client.post("/expansion/set_tier", json={"tier_index": 2})
        
        assert res.status_code == 200
        assert res.json()["success"] == True
        ctx.expansion_policy.set_tier.assert_called_with(2)
