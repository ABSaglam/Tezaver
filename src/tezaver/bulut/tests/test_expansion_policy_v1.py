# Tezaver Bulut - Expansion Policy Unit Tests (P6)
"""
Tests for ExpansionPolicyService tier management.
"""
import pytest
from unittest.mock import MagicMock

from tezaver.bulut.core.expansion_policy import (
    ExpansionPolicyService, 
    ExpansionTier,
    ExpansionBlockReason
)


class TestExpansionPolicy:
    """Tests for ExpansionPolicyService."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.config.expansion_enabled = True
        ctx.config.expansion_min_net_pnl_for_stepup = 0.0
        ctx.config.expansion_block_if_critical_alerts = True
        
        # Persistence
        ctx.persistence.get_expansion_state.return_value = None
        ctx.persistence.update_expansion_state = MagicMock()
        ctx.persistence.get_recent_alerts.return_value = []
        
        # Proof ladder
        ctx.proof_ladder.current_step = 5
        
        # Constitution guard
        ctx.constitution_guard.is_compliant.return_value = True
        
        # Strict timing
        ctx.strict_timing.is_healthy.return_value = True
        
        # Telemetry
        ctx.telemetry = MagicMock()
        
        return ctx
    
    def test_initial_tier_is_t0(self, mock_ctx):
        """Initial tier should be T0_PILOT."""
        service = ExpansionPolicyService(mock_ctx)
        
        assert service.get_current_tier() == ExpansionTier.T0_PILOT
        assert service.get_tier_limit() == 50.0
    
    def test_can_step_up_all_pass(self, mock_ctx):
        """Step up allowed when all conditions pass."""
        service = ExpansionPolicyService(mock_ctx)
        
        can, reasons = service.can_step_up()
        
        assert can == True
        assert len(reasons) == 0
    
    def test_blocks_proof_insufficient(self, mock_ctx):
        """Blocks step up when proof ladder step is insufficient."""
        mock_ctx.proof_ladder.current_step = 1
        service = ExpansionPolicyService(mock_ctx)
        
        can, reasons = service.can_step_up()
        
        assert can == False
        assert ExpansionBlockReason.PROOF_INSUFFICIENT in reasons
    
    def test_blocks_critical_alerts(self, mock_ctx):
        """Blocks step up when critical alerts present."""
        mock_ctx.persistence.get_recent_alerts.return_value = [
            {"severity": 1, "level": "BLOCK"}
        ]
        service = ExpansionPolicyService(mock_ctx)
        
        can, reasons = service.can_step_up()
        
        assert can == False
        assert ExpansionBlockReason.CRITICAL_ALERTS in reasons
    
    def test_blocks_constitution_fail(self, mock_ctx):
        """Blocks step up when constitution guard fails."""
        mock_ctx.constitution_guard.is_compliant.return_value = False
        service = ExpansionPolicyService(mock_ctx)
        
        can, reasons = service.can_step_up()
        
        assert can == False
        assert ExpansionBlockReason.CONSTITUTION_FAIL in reasons
    
    def test_blocks_strict_timing_unhealthy(self, mock_ctx):
        """Blocks step up when strict timing is unhealthy."""
        mock_ctx.strict_timing.is_healthy.return_value = False
        service = ExpansionPolicyService(mock_ctx)
        
        can, reasons = service.can_step_up()
        
        assert can == False
        assert ExpansionBlockReason.STRICT_TIMING_UNHEALTHY in reasons
    
    def test_step_up_success(self, mock_ctx):
        """Step up succeeds and updates tier."""
        service = ExpansionPolicyService(mock_ctx)
        
        success, error = service.step_up()
        
        assert success == True
        assert error is None
        mock_ctx.persistence.update_expansion_state.assert_called()
    
    def test_step_up_tier_progression(self, mock_ctx):
        """Tier progresses from T0 -> T1 -> T2."""
        # Start at T0
        mock_ctx.persistence.get_expansion_state.return_value = {"current_tier": 0}
        service = ExpansionPolicyService(mock_ctx)
        
        # After step up should be T1
        success, _ = service.step_up()
        assert success
        call_args = mock_ctx.persistence.update_expansion_state.call_args[0][0]
        assert call_args["current_tier"] == 1
    
    def test_blocks_at_max_tier(self, mock_ctx):
        """Cannot step up from max tier."""
        mock_ctx.persistence.get_expansion_state.return_value = {"current_tier": 2}
        service = ExpansionPolicyService(mock_ctx)
        
        can, reasons = service.can_step_up()
        
        assert can == False
        assert ExpansionBlockReason.ALREADY_MAX_TIER in reasons
    
    def test_set_tier_override(self, mock_ctx):
        """Set tier forcefully bypasses gating."""
        service = ExpansionPolicyService(mock_ctx)
        
        success, error = service.set_tier(2)
        
        assert success == True
        call_args = mock_ctx.persistence.update_expansion_state.call_args[0][0]
        assert call_args["current_tier"] == 2
    
    def test_tier_limits_correct(self, mock_ctx):
        """Verify tier limits are correct."""
        service = ExpansionPolicyService(mock_ctx)
        
        mock_ctx.persistence.get_expansion_state.return_value = {"current_tier": 0}
        assert service.get_tier_limit() == 50.0
        
        mock_ctx.persistence.get_expansion_state.return_value = {"current_tier": 1}
        service._cache = None  # Clear cache
        assert service.get_tier_limit() == 200.0
        
        mock_ctx.persistence.get_expansion_state.return_value = {"current_tier": 2}
        service._cache = None
        assert service.get_tier_limit() == 500.0


class TestPilotMeterWithExpansion:
    """Tests for PilotMeter integration with ExpansionPolicy."""
    
    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies."""
        persistence = MagicMock()
        persistence.get_pilot_state.return_value = None
        persistence.update_pilot_state = MagicMock()
        
        expansion = MagicMock()
        expansion.get_tier_limit.return_value = 200.0
        expansion.get_current_tier.return_value = ExpansionTier.T1_GROWTH
        
        return persistence, expansion
    
    def test_limit_comes_from_expansion(self, mock_deps):
        """Pilot meter uses expansion tier limit."""
        from tezaver.bulut.core.pilot_meter import PilotMeter
        
        persistence, expansion = mock_deps
        meter = PilotMeter(persistence, expansion)
        
        status = meter.get_status()
        
        assert status["limit_usdt"] == 200.0
        assert status["remaining_usdt"] == 200.0
    
    def test_includes_tier_info(self, mock_deps):
        """Status includes tier information."""
        from tezaver.bulut.core.pilot_meter import PilotMeter
        
        persistence, expansion = mock_deps
        meter = PilotMeter(persistence, expansion)
        
        status = meter.get_status()
        
        assert status["current_tier"] == 1
        assert status["current_tier_name"] == "T1_GROWTH"
