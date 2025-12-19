# Tezaver Bulut - Pilot Autopilot Unit Tests (P5)
"""
Tests for PilotMeter and AutopilotService.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta

from tezaver.bulut.core.pilot_meter import PilotMeter
from tezaver.bulut.core.autopilot_service import AutopilotService, AutopilotBlockReason


class TestPilotMeter:
    """Tests for PilotMeter service."""
    
    @pytest.fixture
    def mock_persistence(self):
        """Create mock persistence with pilot state methods."""
        persistence = MagicMock()
        persistence.get_pilot_state.return_value = None
        persistence.update_pilot_state = MagicMock()
        return persistence
    
    def test_initial_status_empty(self, mock_persistence):
        """Initial pilot meter has full limit available."""
        meter = PilotMeter(mock_persistence)
        status = meter.get_status()
        
        assert status["active"] == False
        assert status["limit_usdt"] == 50.0
        assert status["committed_usdt"] == 0.0
        assert status["remaining_usdt"] == 50.0
    
    def test_commit_notional_success(self, mock_persistence):
        """Can commit notional within limit."""
        meter = PilotMeter(mock_persistence)
        
        result = meter.commit_notional(25.0)
        
        assert result == True
        assert mock_persistence.update_pilot_state.called
    
    def test_commit_notional_exceeds_limit(self, mock_persistence):
        """Cannot commit notional exceeding limit."""
        mock_persistence.get_pilot_state.return_value = {
            "start_ts": datetime.now(timezone.utc).isoformat(),
            "committed_usdt": 40.0,
            "last_commit_ts": None
        }
        meter = PilotMeter(mock_persistence)
        
        result = meter.commit_notional(20.0)  # Would exceed 50
        
        assert result == False
    
    def test_is_limit_reached(self, mock_persistence):
        """Detects when pilot limit is reached."""
        mock_persistence.get_pilot_state.return_value = {
            "start_ts": datetime.now(timezone.utc).isoformat(),
            "committed_usdt": 50.0,
            "last_commit_ts": None
        }
        meter = PilotMeter(mock_persistence)
        
        assert meter.is_limit_reached() == True


class TestAutopilotService:
    """Tests for AutopilotService."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context with required services."""
        ctx = MagicMock()
        ctx.config.mode = "REAL_MAINNET"
        
        # Launch checklist
        ctx.launch_checklist.check_all.return_value = {"passed": True}
        
        # Constitution guard
        ctx.constitution_guard.is_compliant.return_value = True
        
        # Strict timing
        ctx.strict_timing.is_healthy.return_value = True
        
        # Proof ladder
        ctx.proof_ladder.current_step = 3
        
        # Pilot meter
        ctx.pilot_meter.is_limit_reached.return_value = False
        ctx.pilot_meter.can_commit.return_value = True
        ctx.pilot_meter.commit_notional.return_value = True
        
        # Telemetry
        ctx.telemetry = MagicMock()
        
        return ctx
    
    def test_can_autopilot_all_pass(self, mock_ctx):
        """Autopilot allowed when all checks pass."""
        service = AutopilotService(mock_ctx)
        
        can, reason = service.check_can_autopilot()
        
        assert can == True
        assert reason is None
    
    def test_blocks_wrong_mode(self, mock_ctx):
        """Blocks autopilot if not REAL_MAINNET mode."""
        mock_ctx.config.mode = "SANDBOX"
        service = AutopilotService(mock_ctx)
        
        can, reason = service.check_can_autopilot()
        
        assert can == False
        assert reason == AutopilotBlockReason.WRONG_MODE
    
    def test_blocks_launch_checklist_fail(self, mock_ctx):
        """Blocks autopilot if launch checklist fails."""
        mock_ctx.launch_checklist.check_all.return_value = {"passed": False}
        service = AutopilotService(mock_ctx)
        
        can, reason = service.check_can_autopilot()
        
        assert can == False
        assert reason == AutopilotBlockReason.LAUNCH_CHECKLIST_FAIL
    
    def test_blocks_pilot_limit_reached(self, mock_ctx):
        """Blocks autopilot if pilot limit is reached."""
        mock_ctx.pilot_meter.is_limit_reached.return_value = True
        service = AutopilotService(mock_ctx)
        
        can, reason = service.check_can_autopilot()
        
        assert can == False
        assert reason == AutopilotBlockReason.PILOT_LIMIT_REACHED
    
    def test_enable_succeeds_when_all_pass(self, mock_ctx):
        """Enable succeeds when all gating checks pass."""
        service = AutopilotService(mock_ctx)
        
        result = service.enable()
        
        assert result == True
        assert service.enabled == True
    
    def test_enable_fails_when_blocked(self, mock_ctx):
        """Enable fails when gating checks fail."""
        mock_ctx.config.mode = "SANDBOX"
        service = AutopilotService(mock_ctx)
        
        result = service.enable()
        
        assert result == False
        assert service.enabled == False
    
    def test_auto_accept_proposed_plans(self, mock_ctx):
        """Auto-accept proposed plans when enabled."""
        service = AutopilotService(mock_ctx)
        service.enable()
        
        # Create mock plan
        plan = MagicMock()
        plan.decision.name = "OPEN"
        plan.notional_usdt = 25.0
        
        accepted = service.auto_accept_proposed_plans([plan])
        
        assert len(accepted) == 1
        assert plan.status == "ACCEPTED"
    
    def test_auto_accept_respects_cycle_limit(self, mock_ctx):
        """Auto-accept respects max entries per cycle."""
        service = AutopilotService(mock_ctx)
        service.enable()
        
        # Create multiple plans
        plans = []
        for i in range(3):
            plan = MagicMock()
            plan.decision.name = "OPEN"
            plan.notional_usdt = 10.0
            plans.append(plan)
        
        accepted = service.auto_accept_proposed_plans(plans)
        
        # MAX_NEW_ENTRIES_PER_CYCLE = 1
        assert len(accepted) == 1
