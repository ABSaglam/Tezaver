# Tezaver Bulut - Daily Ops Tests (P12)
"""
Tests for Daily Ops Report and Health Check services.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from tezaver.bulut.core.daily_ops_report import DailyOpsReportService
from tezaver.bulut.core.health_check_scheduler import HealthCheckScheduler
from tezaver.bulut.core.alert_router import AlertRouter


class TestDailyOpsReportService:
    """Tests for DailyOpsReportService."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.config.mode = "REAL_MAINNET"
        
        # Persistence
        ctx.persistence.get_income_events_for_date.return_value = []
        ctx.persistence.get_order_fills_for_date.return_value = []
        ctx.persistence.get_recovery_reports_for_date.return_value = []
        ctx.persistence.get_alerts_for_date.return_value = []
        ctx.persistence.get_daily_report.return_value = None
        ctx.persistence.save_daily_report = MagicMock()
        
        # Services
        ctx.autopilot_service.get_status.return_value = {"enabled": False}
        ctx.kill_switch.get_events.return_value = []
        ctx.allocation_engine.get_status.return_value = {"total_used_usdt": 25.0}
        ctx.exit_intel_engine.get_recent_decisions.return_value = []
        
        return ctx
    
    def test_compute_today_summary(self, mock_ctx):
        """Test computing today's summary."""
        service = DailyOpsReportService(mock_ctx)
        
        summary = service.compute_today_summary()
        
        assert summary.date == datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert summary.net_pnl == 0.0
        assert summary.created_at is not None
    
    def test_summary_includes_required_fields(self, mock_ctx):
        """Test summary contains all required fields."""
        service = DailyOpsReportService(mock_ctx)
        
        summary = service.compute_today_summary()
        
        # Check all required fields exist
        assert hasattr(summary, "net_pnl")
        assert hasattr(summary, "gross_pnl")
        assert hasattr(summary, "fees")
        assert hasattr(summary, "trades_count")
        assert hasattr(summary, "autopilot_minutes")
        assert hasattr(summary, "kill_switch_events")
        assert hasattr(summary, "recovery_runs")
        assert hasattr(summary, "allocation_peak")
        assert hasattr(summary, "exit_decisions")
        assert hasattr(summary, "alerts_count")
    
    def test_save_report(self, mock_ctx):
        """Test saving report to persistence."""
        service = DailyOpsReportService(mock_ctx)
        summary = service.compute_today_summary()
        
        result = service.save_report(summary)
        
        assert result == True
        mock_ctx.persistence.save_daily_report.assert_called()
    
    def test_get_today_report_dict(self, mock_ctx):
        """Test getting today's report as dict."""
        service = DailyOpsReportService(mock_ctx)
        
        report = service.get_today_report()
        
        assert isinstance(report, dict)
        assert "date" in report
        assert "net_pnl" in report


class TestHealthCheckScheduler:
    """Tests for HealthCheckScheduler."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.config.mode = "DEV"
        ctx.config.max_time_offset_ms = 3000
        
        # Time sync
        ctx.time_sync.server_offset_ms = 100
        ctx.time_sync.last_sync_ts = None
        
        # Kill switch
        ctx.kill_switch.get_status.return_value = {"state": "NORMAL"}
        
        # Recovery
        ctx.restart_recovery.get_status.return_value = {"status": "PASS"}
        
        # Autopilot
        ctx.autopilot_service.get_status.return_value = {"enabled": False}
        
        # Scheduler
        ctx.scheduler.is_running.return_value = True
        
        # Persistence
        ctx.persistence.save_health_check = MagicMock()
        ctx.persistence.insert_alert = MagicMock()
        
        return ctx
    
    def test_run_check_healthy(self, mock_ctx):
        """Test health check returns healthy when no anomalies."""
        scheduler = HealthCheckScheduler(mock_ctx)
        
        result = scheduler.run_check()
        
        assert result["healthy"] == True
        assert len(result["anomalies"]) == 0
    
    def test_run_check_detects_time_skew(self, mock_ctx):
        """Test health check detects time sync skew."""
        mock_ctx.time_sync.server_offset_ms = 15000  # 15 seconds
        scheduler = HealthCheckScheduler(mock_ctx)
        
        result = scheduler.run_check()
        
        assert result["healthy"] == False
        codes = [a["code"] for a in result["anomalies"]]
        assert "TIME_SYNC_SKEW" in codes
    
    def test_run_check_detects_kill_switch(self, mock_ctx):
        """Test health check detects non-normal kill switch."""
        mock_ctx.kill_switch.get_status.return_value = {"state": "HALTED"}
        scheduler = HealthCheckScheduler(mock_ctx)
        
        result = scheduler.run_check()
        
        codes = [a["code"] for a in result["anomalies"]]
        assert "KILL_SWITCH_ACTIVE" in codes
    
    def test_saves_check_to_persistence(self, mock_ctx):
        """Test health check is saved to persistence."""
        scheduler = HealthCheckScheduler(mock_ctx)
        
        scheduler.run_check()
        
        mock_ctx.persistence.save_health_check.assert_called()


class TestAlertRouter:
    """Tests for AlertRouter."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.persistence.get_recent_alerts.return_value = []
        return ctx
    
    def test_route_alert_normalizes_level(self, mock_ctx):
        """Test alert level normalization."""
        router = AlertRouter(mock_ctx)
        
        routed = router.route_alert({"level": "critical", "message": "test"})
        
        assert routed.level == "BLOCK"
    
    def test_route_alert_maps_action(self, mock_ctx):
        """Test alert action mapping."""
        router = AlertRouter(mock_ctx)
        
        routed = router.route_alert({
            "source": "health_check",
            "message": "Recovery failed",
            "context_json": '{"code": "RECOVERY_FAILED"}'
        })
        
        assert routed.recommended_action is not None
        assert "/recovery/run" in (routed.action_endpoint or "")
    
    def test_get_top_alerts(self, mock_ctx):
        """Test getting top alerts."""
        mock_ctx.persistence.get_recent_alerts.return_value = [
            {"id": 1, "level": "WARN", "message": "test", "source": "test"}
        ]
        router = AlertRouter(mock_ctx)
        
        alerts = router.get_top_alerts(limit=10)
        
        assert len(alerts) == 1
