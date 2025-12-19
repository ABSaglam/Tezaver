# Tezaver Bulut - Runbook Snapshot Tests (P11)
"""
Tests for Runbook snapshot API.
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
            ctx.config.strict_timing_enabled = True
            ctx.config.max_drift_ms = 5000
            ctx.config.allowed_hosts = ["*"]
            ctx.config.rate_limiter_enabled = False  # Disable rate limiter in tests
            
            # State
            ctx.state.pattern_pack_loaded = True
            ctx.state.trade_locked = False
            
            # Mock dependencies
            ctx.persistence = MagicMock()
            ctx.persistence.get_positions.return_value = []
            ctx.persistence.get_recent_cycles.return_value = []
            ctx.telemetry = MagicMock()
            ctx.scheduler = MagicMock()
            ctx.scheduler.start = AsyncMock()
            ctx.scheduler.stop = AsyncMock()
            ctx.time_sync = MagicMock()
            ctx.time_sync.refresh = AsyncMock()
            ctx.time_sync.last_sync_ts = None
            ctx.time_sync.server_offset_ms = 0
            ctx.exchangeinfo_cache = MagicMock()
            ctx.exchangeinfo_cache.refresh = AsyncMock()
            ctx.exchangeinfo_cache.symbols_count.return_value = 500
            ctx.task_supervisor = MagicMock()
            ctx.task_supervisor.start_all = AsyncMock()
            ctx.task_supervisor.stop_all = AsyncMock()
            ctx.reconciliation_service = MagicMock()
            ctx.reconciliation_service.reconcile = AsyncMock(return_value={"status": "OK"})
            ctx.executor = MagicMock()
            ctx.executor.recover_executing_plans = AsyncMock()
            ctx.constitution_guard = MagicMock()
            ctx.constitution_guard.enabled = True
            ctx.constitution_guard.is_locked.return_value = False
            ctx.drift_guard = MagicMock()
            ctx.drift_guard.enabled = True
            ctx.drift_guard.is_compliant.return_value = True
            ctx.migration_runner = MagicMock()
            
            # Runbook-specific mocks
            ctx.launch_checklist = MagicMock()
            ctx.launch_checklist.is_passed.return_value = True
            ctx.launch_checklist.passed_count.return_value = 10
            ctx.launch_checklist.total_count.return_value = 10
            
            ctx.proof_ladder = MagicMock()
            ctx.proof_ladder.current_step = 3
            ctx.proof_ladder.total_steps = 5
            
            ctx.pilot_meter = MagicMock()
            ctx.pilot_meter.get_status.return_value = {"committed_usdt": 25, "limit_usdt": 50}
            
            ctx.expansion_policy = MagicMock()
            ctx.expansion_policy.get_status.return_value = {"current_tier": 0, "tier_limit": 50}
            
            ctx.autopilot_service = MagicMock()
            ctx.autopilot_service.get_status.return_value = {"enabled": False}
            
            ctx.allocation_engine = MagicMock()
            ctx.allocation_engine.get_status.return_value = {"total_used_usdt": 20}
            
            ctx.exit_intel_engine = MagicMock()
            ctx.exit_intel_engine.get_status.return_value = {"profiles_loaded": 2}
            
            ctx.kill_switch = MagicMock()
            ctx.kill_switch.get_status.return_value = {"state": "NORMAL"}
            
            ctx.restart_recovery = MagicMock()
            ctx.restart_recovery.get_status.return_value = {"status": "PASS", "can_resume": True}

            mock_bootstrap.return_value = ctx

            client = TestClient(app, base_url="http://localhost:8000")
            
            yield client, ctx


def test_snapshot_returns_ok(app_client):
    """Test GET /runbook/snapshot returns ok status."""
    client, ctx = app_client
    
    with client:
        res = client.get("/runbook/snapshot")
        
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") == True


def test_snapshot_contains_required_keys(app_client):
    """Test snapshot contains all 12 module keys."""
    client, ctx = app_client
    
    required_keys = [
        "mode",
        "constitution",
        "drift_guard",
        "strict_timing",
        "time_sync",
        "exchangeinfo",
        "launch_checklist",
        "proof_ladder",
        "pilot_meter",
        "expansion",
        "autopilot",
        "allocation",
        "exit_intel",
        "kill_switch",
        "recovery",
        "forensics",
        "test_reports"
    ]
    
    with client:
        res = client.get("/runbook/snapshot")
        data = res.json()
        
        for key in required_keys:
            assert key in data, f"Missing key: {key}"


def test_snapshot_mode_info(app_client):
    """Test snapshot contains mode information."""
    client, ctx = app_client
    
    with client:
        res = client.get("/runbook/snapshot")
        data = res.json()
        
        assert data["mode"]["current"] == "REAL_MAINNET"
        assert data["mode"]["is_mainnet"] == True


def test_snapshot_kill_switch_state(app_client):
    """Test snapshot contains kill switch state."""
    client, ctx = app_client
    
    with client:
        res = client.get("/runbook/snapshot")
        data = res.json()
        
        assert data["kill_switch"]["state"] == "NORMAL"


def test_snapshot_recovery_status(app_client):
    """Test snapshot contains recovery status."""
    client, ctx = app_client
    
    with client:
        res = client.get("/runbook/snapshot")
        data = res.json()
        
        assert data["recovery"]["status"] == "PASS"
        assert data["recovery"]["can_resume"] == True
