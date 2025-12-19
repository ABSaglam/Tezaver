# Tezaver Bulut - Recovery Service Unit Tests (P10)
"""
Tests for RestartRecoveryService safe boot and reconciliation.
"""
import pytest
from unittest.mock import MagicMock

from tezaver.bulut.core.restart_recovery import (
    RestartRecoveryService, RecoveryStatus, RecoveryBlocker
)


class TestRestartRecoveryService:
    """Tests for RestartRecoveryService."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.config.mode = "REAL_MAINNET"
        ctx.config.recovery_safe_boot = True
        ctx.config.recovery_block_resume_if_stale = True
        
        # Persistence
        ctx.persistence.get_latest_recovery_report.return_value = None
        ctx.persistence.save_recovery_report = MagicMock()
        ctx.persistence.get_positions.return_value = []
        ctx.persistence.get_trade_plans.return_value = []
        
        # Kill switch
        ctx.kill_switch = MagicMock()
        ctx.kill_switch.safe.return_value = (True, "Safe mode activated")
        ctx.kill_switch.get_status.return_value = {"state": "SAFE"}
        
        # Reconciliation - return clean result by default
        ctx.reconciliation_service = MagicMock()
        ctx.reconciliation_service.reconcile_positions.return_value = {
            "synced": 0,
            "errors": []  # Empty list = no errors
        }
        
        # Telemetry
        ctx.telemetry = MagicMock()
        
        # Strict timing / drift guard
        ctx.strict_timing = MagicMock()
        ctx.strict_timing.is_healthy.return_value = True
        ctx.drift_guard = MagicMock()
        ctx.drift_guard.is_compliant.return_value = True
        
        return ctx
    
    def test_initial_status_not_run(self, mock_ctx):
        """Initial status should be NOT_RUN."""
        recovery = RestartRecoveryService(mock_ctx)
        
        status = recovery.get_status()
        assert status["status"] == "NOT_RUN"
        assert status["can_resume"] == False
    
    def test_safe_boot_enters_safe_mode(self, mock_ctx):
        """Safe boot should trigger kill switch SAFE."""
        recovery = RestartRecoveryService(mock_ctx)
        
        success, msg = recovery.safe_boot()
        
        assert success == True
        mock_ctx.kill_switch.safe.assert_called()
    
    def test_safe_boot_skipped_in_non_trading_mode(self, mock_ctx):
        """Safe boot should be skipped when not in trading mode."""
        mock_ctx.config.mode = "DEV"
        recovery = RestartRecoveryService(mock_ctx)
        
        success, msg = recovery.safe_boot()
        
        assert success == True
        assert "skipped" in msg.lower()
        mock_ctx.kill_switch.safe.assert_not_called()
    
    def test_run_recovery_pass(self, mock_ctx):
        """Run recovery should pass when no critical blockers."""
        recovery = RestartRecoveryService(mock_ctx)
        
        report = recovery.run()
        
        assert report.status == RecoveryStatus.PASS
        assert len([b for b in report.blockers if b.severity == "CRITICAL"]) == 0
    
    def test_run_recovery_fail_with_critical(self, mock_ctx):
        """Run recovery should fail with critical blockers."""
        mock_ctx.reconciliation_service.reconcile_positions.return_value = {
            "synced": 0,
            "errors": ["Exchange timeout"]
        }
        recovery = RestartRecoveryService(mock_ctx)
        
        report = recovery.run()
        
        assert report.status == RecoveryStatus.FAIL
        critical = [b for b in report.blockers if b.severity == "CRITICAL"]
        assert len(critical) > 0
    
    def test_can_resume_after_pass(self, mock_ctx):
        """Can resume should be True after PASS recovery."""
        recovery = RestartRecoveryService(mock_ctx)
        recovery.run()
        
        can, reasons = recovery.can_resume()
        
        assert can == True
        assert len(reasons) == 0
    
    def test_cannot_resume_after_fail(self, mock_ctx):
        """Can resume should be False after FAIL recovery."""
        mock_ctx.reconciliation_service.reconcile_positions.return_value = {
            "errors": ["Critical error"]
        }
        recovery = RestartRecoveryService(mock_ctx)
        recovery.run()
        
        can, reasons = recovery.can_resume()
        
        assert can == False
        assert len(reasons) > 0
    
    def test_recovery_saves_report(self, mock_ctx):
        """Run should save recovery report."""
        recovery = RestartRecoveryService(mock_ctx)
        
        recovery.run()
        
        mock_ctx.persistence.save_recovery_report.assert_called()
    
    def test_recovery_emits_telemetry(self, mock_ctx):
        """Run should emit telemetry."""
        recovery = RestartRecoveryService(mock_ctx)
        
        recovery.run()
        
        mock_ctx.telemetry.emit.assert_called()
