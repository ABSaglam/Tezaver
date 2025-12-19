# Tezaver Bulut - Exit Intel API Tests (P8)
"""
Tests for Exit Intel REST endpoints.
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
            
            # Exit Intel Engine
            ctx.exit_intel_engine = MagicMock()
            ctx.exit_intel_engine.get_status.return_value = {
                "profiles_loaded": 2,
                "profile_ids": ["global_default", "global_atr"],
                "decisions_count": 5
            }
            ctx.exit_intel_engine.get_decisions.return_value = [
                {"symbol": "BTCUSDT", "computed_sl": 49000, "timestamp": "2024-01-01T00:00:00Z"}
            ]
            ctx.exit_intel_engine.preview_exit.return_value = {
                "symbol": "BTCUSDT",
                "entry_price": 50000.0,
                "sl_price": 49000.0,
                "tp_price": 52000.0,
                "profile_id": "global_default",
                "profile_name": "Global Default",
                "rules_summary": ["fixed_pct", "time_stop"]
            }

            mock_bootstrap.return_value = ctx

            client = TestClient(app, base_url="http://localhost:8000")
            
            yield client, ctx


def test_get_exit_status(app_client):
    """Test GET /exits/status returns expected shape."""
    client, ctx = app_client
    
    with client:
        res = client.get("/exits/status")
        
        assert res.status_code == 200
        data = res.json()
        assert "profiles_loaded" in data
        assert "profile_ids" in data


def test_get_decisions(app_client):
    """Test GET /exits/decisions/latest returns decisions."""
    client, ctx = app_client
    
    with client:
        res = client.get("/exits/decisions/latest?limit=10")
        
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)


def test_preview_exit(app_client):
    """Test POST /exits/preview returns computed levels."""
    client, ctx = app_client
    
    with client:
        res = client.post("/exits/preview", json={
            "symbol": "BTCUSDT",
            "entry_price": 50000.0,
            "side": "LONG"
        })
        
        assert res.status_code == 200
        data = res.json()
        assert "sl_price" in data
        assert "tp_price" in data
        assert "profile_id" in data
