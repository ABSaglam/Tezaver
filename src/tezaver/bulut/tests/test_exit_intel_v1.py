# Tezaver Bulut - Exit Intel Engine Unit Tests (P8)
"""
Tests for ExitIntelEngine profile resolution and level computation.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from tezaver.bulut.core.exit_intel_engine import ExitIntelEngine
from tezaver.bulut.schemas.exit_profile_v2 import (
    ExitProfileV2, ComputedExitLevels,
    FixedPctRule, AtrStopRule, TrailingStopRule, BreakEvenRule
)


class TestExitIntelEngine:
    """Tests for ExitIntelEngine."""
    
    @pytest.fixture
    def mock_ctx(self):
        """Create mock context."""
        ctx = MagicMock()
        ctx.persistence.get_exit_profiles.return_value = []
        return ctx
    
    def test_default_profile_loaded(self, mock_ctx):
        """Default global profile is loaded."""
        engine = ExitIntelEngine(mock_ctx)
        
        assert "global_default" in engine._profiles
        assert "global_atr" in engine._profiles
    
    def test_resolve_profile_global_fallback(self, mock_ctx):
        """Falls back to global when no specific match."""
        engine = ExitIntelEngine(mock_ctx)
        
        profile = engine.resolve_profile("BTCUSDT", None)
        
        assert profile.profile_id in ["global_default", "global_atr"]
    
    def test_fixed_pct_computes_sl_tp(self, mock_ctx):
        """Fixed percentage rule computes SL/TP correctly."""
        engine = ExitIntelEngine(mock_ctx)
        
        position = {
            "position_id": "test1",
            "symbol": "BTCUSDT",
            "entry_price": 50000.0,
            "side": "LONG",
            "open_ts": datetime.now(timezone.utc).isoformat()
        }
        
        levels = engine.compute_exit_levels(position)
        
        # Default fixed_pct: 2% SL, 4% TP
        assert levels.sl_price is not None
        assert levels.tp_price is not None
        assert levels.sl_price < 50000.0  # Below entry for long
        assert levels.tp_price > 50000.0  # Above entry for long
    
    def test_atr_stop_with_atr_value(self, mock_ctx):
        """ATR stop uses provided ATR value."""
        mock_ctx.persistence.get_exit_profiles.return_value = [{
            "profile_id": "atr_test",
            "name": "ATR Test",
            "rules": [{"type": "atr_stop", "sl_atr_mult": 1.5, "tp_atr_mult": 3.0}],
            "priority": 100
        }]
        engine = ExitIntelEngine(mock_ctx)
        
        position = {
            "position_id": "test2",
            "symbol": "BTCUSDT",
            "entry_price": 50000.0,
            "side": "LONG",
            "open_ts": datetime.now(timezone.utc).isoformat()
        }
        
        levels = engine.compute_exit_levels(position, atr_value=500.0)
        
        # SL = 50000 - (500 * 1.5) = 49250
        # TP = 50000 + (500 * 3.0) = 51500
        assert levels.sl_price == pytest.approx(49250.0, rel=0.01)
        assert levels.tp_price == pytest.approx(51500.0, rel=0.01)
    
    def test_trailing_stop_activates(self, mock_ctx):
        """Trailing stop activates when profit threshold reached."""
        engine = ExitIntelEngine(mock_ctx)
        
        # Add trailing stop profile
        engine._profiles["trail_test"] = ExitProfileV2(
            profile_id="trail_test",
            name="Trail Test",
            rules=[{"type": "trailing_stop", "activation_pct": 1.0, "trail_pct": 0.5}],
            priority=100
        )
        
        position = {
            "position_id": "test3",
            "symbol": "BTCUSDT",
            "entry_price": 50000.0,
            "side": "LONG",
            "open_ts": datetime.now(timezone.utc).isoformat()
        }
        
        # Current price 2% above entry - should activate
        levels = engine.compute_exit_levels(position, current_price=51000.0)
        
        assert levels.trailing_active == True
        assert levels.trailing_sl is not None
    
    def test_break_even_triggers(self, mock_ctx):
        """Break even moves SL to entry when triggered."""
        engine = ExitIntelEngine(mock_ctx)
        
        # Add break even profile
        engine._profiles["be_test"] = ExitProfileV2(
            profile_id="be_test",
            name="BE Test",
            rules=[
                {"type": "fixed_pct", "sl_pct": 2.0, "tp_pct": 4.0},
                {"type": "break_even", "at_profit_pct": 1.0, "move_sl_to_entry": True, "buffer_pct": 0.1}
            ],
            priority=100
        )
        
        position = {
            "position_id": "test4",
            "symbol": "BTCUSDT",
            "entry_price": 50000.0,
            "side": "LONG",
            "open_ts": datetime.now(timezone.utc).isoformat()
        }
        
        # Current price 1.5% above entry - should trigger BE
        levels = engine.compute_exit_levels(position, current_price=50750.0)
        
        assert levels.break_even_triggered == True
        # SL should be moved to entry + buffer
        assert levels.sl_price >= 50000.0
    
    def test_time_stop_computed(self, mock_ctx):
        """Time stop computes expiry time."""
        engine = ExitIntelEngine(mock_ctx)
        
        open_time = datetime.now(timezone.utc)
        position = {
            "position_id": "test5",
            "symbol": "BTCUSDT",
            "entry_price": 50000.0,
            "side": "LONG",
            "open_ts": open_time.isoformat()
        }
        
        levels = engine.compute_exit_levels(position)
        
        assert levels.time_stop_due is not None
    
    def test_short_position_inverts(self, mock_ctx):
        """Short positions have inverted SL/TP."""
        engine = ExitIntelEngine(mock_ctx)
        
        position = {
            "position_id": "test6",
            "symbol": "BTCUSDT",
            "entry_price": 50000.0,
            "side": "SHORT",
            "open_ts": datetime.now(timezone.utc).isoformat()
        }
        
        levels = engine.compute_exit_levels(position)
        
        # For short: SL above entry, TP below entry
        assert levels.sl_price > 50000.0
        assert levels.tp_price < 50000.0
    
    def test_decisions_recorded(self, mock_ctx):
        """Exit decisions are recorded."""
        engine = ExitIntelEngine(mock_ctx)
        
        position = {
            "position_id": "test7",
            "symbol": "BTCUSDT",
            "entry_price": 50000.0,
            "side": "LONG",
            "open_ts": datetime.now(timezone.utc).isoformat()
        }
        
        engine.compute_exit_levels(position)
        
        decisions = engine.get_decisions()
        assert len(decisions) >= 1
        assert decisions[0]["symbol"] == "BTCUSDT"
    
    def test_preview_exit(self, mock_ctx):
        """Preview exit without real position."""
        engine = ExitIntelEngine(mock_ctx)
        
        preview = engine.preview_exit(
            symbol="ETHUSDT",
            entry_price=3000.0,
            side="LONG"
        )
        
        assert preview["symbol"] == "ETHUSDT"
        assert preview["sl_price"] is not None
        assert preview["tp_price"] is not None
