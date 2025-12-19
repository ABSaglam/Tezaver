# Tezaver Bulut - Performance & Cost Guard Tests (P13)
"""
Tests for PerfCostGuardService.
"""
import pytest
from unittest.mock import MagicMock

from tezaver.bulut.core.perf_cost_guard import (
    PerfCostGuardService, PerfCostMode
)


class TestPerfCostGuardService:
    """Tests for PerfCostGuardService."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.config.mode = "REAL_MAINNET"
        
        # Governor
        ctx.governor = MagicMock()
        ctx.governor.get_market_usage_ratio.return_value = 0.3
        ctx.governor.get_trade_usage_ratio.return_value = 0.2
        
        # Persistence
        ctx.persistence.save_perf_cost_snapshot = MagicMock()
        
        # Telemetry
        ctx.telemetry = MagicMock()
        
        return ctx
    
    def test_initial_mode_is_normal(self, mock_ctx):
        """Initial mode should be NORMAL."""
        guard = PerfCostGuardService(mock_ctx)
        
        status = guard.get_status()
        
        assert status["mode"] == "NORMAL"
    
    def test_record_cycle_updates_avg(self, mock_ctx):
        """Recording cycles updates moving average."""
        guard = PerfCostGuardService(mock_ctx)
        
        guard.record_cycle(1000)
        guard.record_cycle(2000)
        guard.record_cycle(3000)
        
        avg = guard.get_cycle_avg_ms()
        assert avg == 2000.0
    
    def test_high_budget_triggers_degraded(self, mock_ctx):
        """High budget usage triggers DEGRADED mode."""
        mock_ctx.governor.get_market_usage_ratio.return_value = 0.88
        guard = PerfCostGuardService(mock_ctx)
        
        status = guard.evaluate()
        
        assert status.mode == PerfCostMode.DEGRADED
        assert any("budget" in r.lower() for r in status.reasons)
    
    def test_critical_budget_triggers_emergency(self, mock_ctx):
        """Critical budget usage triggers EMERGENCY mode."""
        mock_ctx.governor.get_market_usage_ratio.return_value = 0.96
        guard = PerfCostGuardService(mock_ctx)
        
        status = guard.evaluate()
        
        assert status.mode == PerfCostMode.EMERGENCY
    
    def test_high_cycle_time_triggers_degraded(self, mock_ctx):
        """High cycle time triggers DEGRADED mode."""
        guard = PerfCostGuardService(mock_ctx)
        
        # Record slow cycles
        for _ in range(5):
            guard.record_cycle(12000)  # 12 seconds
        
        status = guard.evaluate()
        
        assert status.mode == PerfCostMode.DEGRADED
        assert any("cycle" in r.lower() for r in status.reasons)
    
    def test_force_mode_overrides_automatic(self, mock_ctx):
        """Force mode overrides automatic evaluation."""
        guard = PerfCostGuardService(mock_ctx)
        
        guard.force_mode(PerfCostMode.EMERGENCY, "Manual test")
        status = guard.evaluate()
        
        assert status.mode == PerfCostMode.EMERGENCY
        assert any("forced" in r.lower() for r in status.reasons)
    
    def test_clear_force_returns_to_normal(self, mock_ctx):
        """Clearing force mode returns to automatic."""
        guard = PerfCostGuardService(mock_ctx)
        
        guard.force_mode(PerfCostMode.EMERGENCY)
        guard.clear_force()
        status = guard.evaluate()
        
        # With normal budgets, should be NORMAL
        assert status.mode == PerfCostMode.NORMAL
    
    def test_recommendations_vary_by_mode(self, mock_ctx):
        """Recommendations differ for each mode."""
        guard = PerfCostGuardService(mock_ctx)
        
        # Normal mode
        normal_recs = guard._get_recommendations(PerfCostMode.NORMAL)
        
        # Emergency mode
        emergency_recs = guard._get_recommendations(PerfCostMode.EMERGENCY)
        
        assert normal_recs.scan_topk > emergency_recs.scan_topk
        assert normal_recs.poll_interval_ms < emergency_recs.poll_interval_ms
    
    def test_get_overrides_returns_dict(self, mock_ctx):
        """Get overrides returns scheduler parameters."""
        guard = PerfCostGuardService(mock_ctx)
        
        overrides = guard.get_overrides()
        
        assert "SCAN_TOPK" in overrides
        assert "POLL_INTERVAL" in overrides
        assert "CATCHUP_MAX_BARS" in overrides
    
    def test_saves_snapshot_on_evaluate(self, mock_ctx):
        """Evaluate saves snapshot to persistence."""
        guard = PerfCostGuardService(mock_ctx)
        
        guard.evaluate()
        
        mock_ctx.persistence.save_perf_cost_snapshot.assert_called()
    
    def test_emits_telemetry_on_evaluate(self, mock_ctx):
        """Evaluate emits telemetry event."""
        guard = PerfCostGuardService(mock_ctx)
        
        guard.evaluate()
        
        mock_ctx.telemetry.emit.assert_called()
