# Tezaver Bulut - Kill Switch Unit Tests (P9)
"""
Tests for KillSwitchService emergency controls.
"""
import pytest
from unittest.mock import MagicMock

from tezaver.bulut.core.kill_switch import KillSwitchService, KillSwitchState


class TestKillSwitchService:
    """Tests for KillSwitchService."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.config.mode = "REAL_TESTNET"
        ctx.config.allow_flatten_on_testnet = True
        ctx.config.kill_switch_auto_export_incident = False
        
        # Persistence
        ctx.persistence.get_kill_switch_state.return_value = None
        ctx.persistence.update_kill_switch_state = MagicMock()
        ctx.persistence.get_positions.return_value = []
        
        # Autopilot
        ctx.autopilot_service = MagicMock()
        ctx.autopilot_service.disable = MagicMock()
        
        # Telemetry
        ctx.telemetry = MagicMock()
        
        return ctx
    
    def test_initial_state_normal(self, mock_ctx):
        """Initial state should be NORMAL."""
        ks = KillSwitchService(mock_ctx)
        
        status = ks.get_status()
        assert status["state"] == "NORMAL"
        assert status["entries_allowed"] == True
    
    def test_halt_blocks_entries(self, mock_ctx):
        """HALT should block new entries."""
        ks = KillSwitchService(mock_ctx)
        
        success, msg = ks.halt("test halt", "ops_user")
        
        assert success == True
        assert ks.get_status()["state"] == "HALTED"
        
        allowed, reason = ks.check_entries_allowed()
        assert allowed == False
        assert "KILL_SWITCH" in reason
    
    def test_halt_idempotent(self, mock_ctx):
        """Repeated HALT calls should be safe."""
        ks = KillSwitchService(mock_ctx)
        
        ks.halt("first", "ops1")
        success, msg = ks.halt("second", "ops2")
        
        assert success == True
        assert "Already halted" in msg
    
    def test_safe_mode(self, mock_ctx):
        """SAFE mode should block entries but maintain monitoring."""
        ks = KillSwitchService(mock_ctx)
        
        success, msg = ks.safe("safe test", "ops_user")
        
        assert success == True
        assert ks.get_status()["state"] == "SAFE"
        
        allowed, _ = ks.check_entries_allowed()
        assert allowed == False
    
    def test_flatten_generates_close_plans(self, mock_ctx):
        """FLATTEN should generate close plans for open positions."""
        mock_ctx.persistence.get_positions.return_value = [
            {"symbol": "BTCUSDT", "side": "LONG", "quantity": 0.1, "position_id": "p1"},
            {"symbol": "ETHUSDT", "side": "SHORT", "quantity": 1.0, "position_id": "p2"}
        ]
        ks = KillSwitchService(mock_ctx)
        
        success, msg, plans = ks.flatten("flatten test", "ops_user")
        
        assert success == True
        assert len(plans) == 2
        assert plans[0]["side"] == "SELL"  # Close LONG
        assert plans[1]["side"] == "BUY"   # Close SHORT
        assert all(p["reduce_only"] == True for p in plans)
    
    def test_flatten_no_positions(self, mock_ctx):
        """FLATTEN with no positions should go directly to FLAT."""
        ks = KillSwitchService(mock_ctx)
        
        success, msg, plans = ks.flatten("flatten test", "ops_user")
        
        assert success == True
        assert len(plans) == 0
        assert ks.get_status()["state"] == "FLAT"
    
    def test_resume_from_halted(self, mock_ctx):
        """RESUME should return to NORMAL from HALTED."""
        ks = KillSwitchService(mock_ctx)
        ks.halt("test", "ops")
        
        success, msg = ks.resume("resuming", "ops_user")
        
        assert success == True
        assert ks.get_status()["state"] == "NORMAL"
    
    def test_cannot_resume_from_flattening(self, mock_ctx):
        """Cannot RESUME while FLATTENING."""
        mock_ctx.persistence.get_positions.return_value = [
            {"symbol": "BTCUSDT", "side": "LONG", "quantity": 0.1}
        ]
        ks = KillSwitchService(mock_ctx)
        ks.flatten("test", "ops")
        
        success, msg = ks.resume("trying resume", "ops_user")
        
        assert success == False
        assert "wait for completion" in msg.lower()
    
    def test_halt_disables_autopilot(self, mock_ctx):
        """HALT should disable autopilot."""
        ks = KillSwitchService(mock_ctx)
        
        ks.halt("test halt", "ops_user")
        
        mock_ctx.autopilot_service.disable.assert_called()
    
    def test_events_recorded(self, mock_ctx):
        """Kill switch events should be recorded."""
        ks = KillSwitchService(mock_ctx)
        
        ks.halt("halt reason", "operator")
        ks.resume("resume reason", "operator")
        
        events = ks.get_events()
        
        assert len(events) >= 2
        assert events[0]["event_type"] == "RESUME"
