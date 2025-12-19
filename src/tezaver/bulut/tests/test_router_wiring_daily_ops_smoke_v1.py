# Tezaver Bulut - Daily Ops Router Wiring Smoke Test (P12)
"""
Smoke tests to ensure Daily Ops endpoints are properly wired.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch

from tezaver.bulut.app_backend import app
from tezaver.bulut.core.context import BulutContext


@pytest.fixture
def daily_ops_client():
    """Create test client with mocked context for Daily Ops routes."""
    
    async def noop_auth(request, config):
        pass
    
    with patch("tezaver.bulut.app_backend.check_ops_auth", noop_auth):
        with patch("tezaver.bulut.app_backend.bootstrap_context") as mock_bootstrap:
            ctx = MagicMock(spec=BulutContext)
            
            # Basic config
            ctx.config.mode = "DEV"
            ctx.config.time_sync_enabled = False
            ctx.config.exchangeinfo_refresh_on_start = False
            ctx.config.startup_selftest_enabled = False
            ctx.config.proof_ladder_auto_evaluate_enabled = False
            ctx.config.user_data_ws_enabled = False
            ctx.config.migrations_enabled = False
            ctx.config.dry_run_enabled = False
            ctx.config.ops_auth_enabled = False
            ctx.config.rate_limiter_enabled = False
            ctx.config.allowed_hosts = ["*"]
            
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
            ctx.reconciliation_service.reconcile = AsyncMock()
            ctx.executor = MagicMock()
            ctx.executor.recover_executing_plans = AsyncMock()
            ctx.constitution_guard = MagicMock()
            ctx.migration_runner = MagicMock()
            
            # Daily Ops specific mocks
            ctx.daily_ops_report = MagicMock()
            ctx.daily_ops_report.get_today_report.return_value = {
                "date": "2024-01-01",
                "net_pnl": 0.0,
                "gross_pnl": 0.0,
                "trades_count": 0,
                "alerts_count": 0,
                "created_at": "2024-01-01T00:00:00Z"
            }
            ctx.daily_ops_report.get_yesterday_report.return_value = {
                "date": "2023-12-31",
                "net_pnl": 0.0,
                "gross_pnl": 0.0,
                "trades_count": 0,
                "alerts_count": 0,
                "created_at": "2024-01-01T00:00:00Z"
            }
            
            ctx.health_check_scheduler = MagicMock()
            ctx.health_check_scheduler.get_status.return_value = {
                "last_check_ts": None,
                "checks_count": 0,
                "interval_seconds": 60
            }
            ctx.health_check_scheduler.get_recent_checks.return_value = []
            ctx.health_check_scheduler.run_check.return_value = {
                "ts": "2024-01-01T00:00:00Z",
                "healthy": True,
                "anomalies": []
            }
            
            ctx.alert_router = MagicMock()
            ctx.alert_router.get_top_alerts.return_value = []

            mock_bootstrap.return_value = ctx

            client = TestClient(app, base_url="http://localhost:8000")
            
            yield client, ctx


def test_daily_ops_today_endpoint(daily_ops_client):
    """Test GET /ops/daily/today returns 200."""
    client, ctx = daily_ops_client
    
    with client:
        res = client.get("/ops/daily/today")
        
        assert res.status_code == 200
        data = res.json()
        assert "date" in data or "error" in data


def test_daily_ops_yesterday_endpoint(daily_ops_client):
    """Test GET /ops/daily/yesterday returns 200."""
    client, ctx = daily_ops_client
    
    with client:
        res = client.get("/ops/daily/yesterday")
        
        assert res.status_code == 200
        data = res.json()
        assert "date" in data or "error" in data


def test_daily_ops_health_status_endpoint(daily_ops_client):
    """Test GET /ops/daily/health/status returns 200."""
    client, ctx = daily_ops_client
    
    with client:
        res = client.get("/ops/daily/health/status")
        
        assert res.status_code == 200


def test_daily_ops_health_checks_endpoint(daily_ops_client):
    """Test GET /ops/daily/health/checks returns 200."""
    client, ctx = daily_ops_client
    
    with client:
        res = client.get("/ops/daily/health/checks")
        
        assert res.status_code == 200
        assert isinstance(res.json(), list)


def test_daily_ops_top_alerts_endpoint(daily_ops_client):
    """Test GET /ops/daily/alerts/top returns 200."""
    client, ctx = daily_ops_client
    
    with client:
        res = client.get("/ops/daily/alerts/top")
        
        assert res.status_code == 200
        assert isinstance(res.json(), list)


def test_daily_ops_compute_endpoint(daily_ops_client):
    """Test POST /ops/daily/compute returns 200."""
    client, ctx = daily_ops_client
    
    # Mock compute and save
    from tezaver.bulut.core.daily_ops_report import DailyReportSummary
    mock_summary = DailyReportSummary(
        date="2024-01-01",
        net_pnl=0.0,
        gross_pnl=0.0,
        fees=0.0,
        funding_income=0.0,
        trades_count=0,
        autopilot_minutes=0,
        kill_switch_events=0,
        recovery_runs=0,
        allocation_peak=0.0,
        exit_decisions=0,
        alerts_count=0,
        created_at="2024-01-01T00:00:00Z"
    )
    ctx.daily_ops_report.compute_today_summary.return_value = mock_summary
    ctx.daily_ops_report.save_report.return_value = True
    ctx.daily_ops_report._summary_to_dict.return_value = {"date": "2024-01-01"}
    
    with client:
        res = client.post("/ops/daily/compute")
        
        assert res.status_code == 200


def test_daily_ops_health_run_endpoint(daily_ops_client):
    """Test POST /ops/daily/health/run returns 200."""
    client, ctx = daily_ops_client
    
    with client:
        res = client.post("/ops/daily/health/run")
        
        assert res.status_code == 200
        data = res.json()
        assert data.get("success") == True
