# Tezaver Bulut - Allocation Engine Unit Tests (P7)
"""
Tests for AllocationEngine budget management.
"""
import pytest
from unittest.mock import MagicMock

from tezaver.bulut.core.allocation_engine import (
    AllocationEngine,
    AllocationDenyReason
)


class TestAllocationEngine:
    """Tests for AllocationEngine."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.config.allocation_symbol_overrides = {}
        ctx.config.allocation_pattern_overrides = {}
        
        # Persistence
        ctx.persistence.get_allocation_state.return_value = None
        ctx.persistence.update_allocation_state = MagicMock()
        
        # Expansion policy (tier limit)
        ctx.expansion_policy.get_tier_limit.return_value = 100.0
        
        # Telemetry
        ctx.telemetry = MagicMock()
        
        return ctx
    
    def test_initial_status_empty(self, mock_ctx):
        """Initial allocation has no usage."""
        engine = AllocationEngine(mock_ctx)
        status = engine.get_status()
        
        assert status["tier_limit_usdt"] == 100.0
        assert status["total_used_usdt"] == 0.0
        assert status["remaining_usdt"] == 100.0
        assert status["symbol_usage"] == {}
    
    def test_check_allocation_allowed(self, mock_ctx):
        """Allocation allowed within limits."""
        engine = AllocationEngine(mock_ctx)
        
        decision = engine.check_allocation("BTCUSDT", "SILVER_BULL", 5.0)
        
        assert decision.allowed == True
        assert decision.deny_reason is None
        assert decision.tier_usage_pct == 5.0
    
    def test_tier_budget_exceeded(self, mock_ctx):
        """Blocks when tier budget exceeded."""
        engine = AllocationEngine(mock_ctx)
        
        decision = engine.check_allocation("BTCUSDT", None, 150.0)
        
        assert decision.allowed == False
        assert decision.deny_reason == AllocationDenyReason.TIER_BUDGET_EXCEEDED.value
    
    def test_symbol_budget_exceeded(self, mock_ctx):
        """Blocks when symbol budget exceeded."""
        engine = AllocationEngine(mock_ctx)
        
        # First allocation OK
        engine.commit_allocation("BTCUSDT", None, 8.0)
        
        # Second should exceed 10% limit
        decision = engine.check_allocation("BTCUSDT", None, 5.0)
        
        assert decision.allowed == False
        assert decision.deny_reason == AllocationDenyReason.SYMBOL_BUDGET_EXCEEDED.value
    
    def test_pattern_budget_exceeded(self, mock_ctx):
        """Blocks when pattern budget exceeded."""
        engine = AllocationEngine(mock_ctx)
        
        # First allocation OK
        engine.commit_allocation("BTCUSDT", "SILVER_BULL", 4.0)
        
        # Second should exceed 5% limit
        decision = engine.check_allocation("ETHUSDT", "SILVER_BULL", 3.0)
        
        assert decision.allowed == False
        assert decision.deny_reason == AllocationDenyReason.PATTERN_BUDGET_EXCEEDED.value
    
    def test_symbol_override_increases_limit(self, mock_ctx):
        """Symbol override increases allowed percentage."""
        mock_ctx.config.allocation_symbol_overrides = {"BTCUSDT": 20.0}
        engine = AllocationEngine(mock_ctx)
        
        # 15% should be allowed with 20% override
        decision = engine.check_allocation("BTCUSDT", None, 15.0)
        
        assert decision.allowed == True
    
    def test_pattern_override_increases_limit(self, mock_ctx):
        """Pattern override increases allowed percentage."""
        mock_ctx.config.allocation_pattern_overrides = {"SILVER_BULL": 10.0}
        engine = AllocationEngine(mock_ctx)
        
        # 8% should be allowed with 10% override
        decision = engine.check_allocation("BTCUSDT", "SILVER_BULL", 8.0)
        
        assert decision.allowed == True
    
    def test_commit_updates_usage(self, mock_ctx):
        """Commit updates usage tracking."""
        engine = AllocationEngine(mock_ctx)
        
        engine.commit_allocation("BTCUSDT", "SILVER_BULL", 10.0)
        
        status = engine.get_status()
        assert status["symbol_usage"]["BTCUSDT"] == 10.0
        assert status["pattern_usage"]["SILVER_BULL"] == 10.0
    
    def test_release_decreases_usage(self, mock_ctx):
        """Release decreases usage tracking."""
        engine = AllocationEngine(mock_ctx)
        
        engine.commit_allocation("BTCUSDT", None, 10.0)
        engine.release_allocation("BTCUSDT", None, 5.0)
        
        status = engine.get_status()
        assert status["symbol_usage"]["BTCUSDT"] == 5.0
    
    def test_decisions_recorded(self, mock_ctx):
        """Allocation decisions are recorded."""
        engine = AllocationEngine(mock_ctx)
        
        engine.check_allocation("BTCUSDT", None, 5.0)
        engine.check_allocation("ETHUSDT", None, 5.0)
        
        decisions = engine.get_decisions(limit=10)
        
        assert len(decisions) == 2
        assert decisions[0]["symbol"] == "ETHUSDT"  # Most recent first
    
    def test_reset_clears_all(self, mock_ctx):
        """Reset clears all usage."""
        engine = AllocationEngine(mock_ctx)
        
        engine.commit_allocation("BTCUSDT", None, 10.0)
        engine.reset()
        
        status = engine.get_status()
        assert status["total_used_usdt"] == 0.0
        assert status["symbol_usage"] == {}
