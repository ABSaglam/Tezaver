# Matrix V2 Telemetry Tests
"""
Tests for telemetry event logging.
"""

import pytest
from pathlib import Path


class TestTelemetryBasic:
    """Basic telemetry tests."""
    
    def test_in_memory_event_sink_logs_events(self):
        """InMemoryEventSink should log and retrieve events."""
        from tezaver.matrix.core.telemetry import (
            InMemoryEventSink,
            MatrixEvent,
            MatrixEventType,
        )
        from tezaver.matrix.core.guardrail import GuardrailEnvironment
        
        sink = InMemoryEventSink()
        assert len(sink) == 0
        
        event = MatrixEvent(
            event_type=MatrixEventType.INFO,
            symbol="BTCUSDT",
            timeframe="15m",
            details={"test": "value"},
        )
        sink.log(event)
        
        assert len(sink) == 1
        events = sink.get_events()
        assert events[0].event_type == MatrixEventType.INFO
        assert events[0].symbol == "BTCUSDT"
    
    def test_matrix_event_to_dict(self):
        """MatrixEvent.to_dict should serialize properly."""
        from tezaver.matrix.core.telemetry import MatrixEvent, MatrixEventType
        from tezaver.matrix.core.guardrail import GuardrailEnvironment
        from datetime import datetime
        
        event = MatrixEvent(
            event_type=MatrixEventType.TICK_START,
            symbol="ETHUSDT",
            timeframe="15m",
            profile_id="ETH_SILVER_15M",
            environment=GuardrailEnvironment.WARGAME,
            tick_index=0,
            details={"note": "test"},
        )
        
        d = event.to_dict()
        assert d["event_type"] == "TICK_START"
        assert d["symbol"] == "ETHUSDT"
        assert d["environment"] == "wargame"
        assert d["details"]["note"] == "test"
    
    def test_unified_engine_logs_tick_events(self):
        """UnifiedEngine should log TICK_START and TICK_END events."""
        from tezaver.matrix.core.telemetry import (
            InMemoryEventSink,
            MatrixEventType,
        )
        from tezaver.matrix.core.engine import UnifiedEngine
        from tezaver.matrix.core.guardrail import GuardrailController, GuardrailConfig
        from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore
        
        # Create minimal components
        class DummyAnalyzer:
            def analyze(self, snapshot):
                return []
        
        class DummyStrategist:
            def evaluate(self, signal, account):
                return None
        
        class DummyExecutor:
            def execute(self, decision, account, snapshot=None):
                return None
        
        sink = InMemoryEventSink()
        store = WargameAccountStore(initial_capital=100.0)
        
        engine = UnifiedEngine(
            profile_id="TEST_PROFILE",
            analyzer=DummyAnalyzer(),
            strategist=DummyStrategist(),
            executor=DummyExecutor(),
            guardrail=GuardrailController(GuardrailConfig()),
            account_store=store,
            event_sink=sink,
        )
        
        # Run one tick with minimal snapshot
        engine.tick({"rsi_15m": 30.0})
        
        events = sink.get_events()
        event_types = [e.event_type for e in events]
        
        # Should have at least TICK_START and TICK_END
        assert MatrixEventType.TICK_START in event_types
        assert MatrixEventType.TICK_END in event_types


class TestWargameEvents:
    """Tests for War Game telemetry integration."""
    
    def _has_patterns(self, symbol: str) -> bool:
        path = Path(f"data/ai_datasets/{symbol}/15m/rally_patterns_v1.parquet")
        return path.exists()
    
    def test_wargame_report_has_telemetry_events(self):
        """WargameReport should contain telemetry events."""
        if not self._has_patterns("BTCUSDT"):
            pytest.skip("BTCUSDT patterns not available")
        
        from tezaver.matrix.wargame.runner import run_silver_15m_from_patterns_for_symbol
        
        report = run_silver_15m_from_patterns_for_symbol(
            symbol="BTCUSDT",
            risk_per_trade_pct=1.0,
            mode="experiment",
        )
        
        # Report should have events
        assert report.events is not None
        assert len(report.events) > 0
        
        # Check for TICK_START and TICK_END events
        event_types = [e.get("event_type") for e in report.events]
        assert "TICK_START" in event_types
        assert "TICK_END" in event_types
