
import tests.mock_env
import unittest
from datetime import datetime
from unittest.mock import MagicMock
from tezaver.matrix.core.telemetry import MatrixEvent, MatrixEventType, InMemoryEventSink
from tezaver.matrix.live.strategy_signal import StrategySignalAdapter, Signal

class TestStrategySignalSchema(unittest.TestCase):
    def test_schema_required_fields(self):
        """Verify STRATEGY_SIGNAL event contains all required fields."""
        sink = InMemoryEventSink()
        # Mock position store
        pos_store = MagicMock()
        adapter = StrategySignalAdapter(position_store=pos_store, event_sink=sink)
        
        # Emit signal
        adapter._emit_signal_event(
            symbol="BTCUSDT",
            tf="15m",
            profile_id="p1",
            bar_close_ts="2025-01-01T12:00:00Z",
            snapshot={"close": 100000},
            signal=Signal.OPEN_LONG,
            reason="TEST_REASON",
            passed_filters=True,
            blocked_by_contract=False,
            cooldown_ok=True,
            filter_result={"in_card_window": True}
        )
        
        self.assertEqual(len(sink.events), 1)
        evt = sink.events[0]
        
        # Check root fields
        self.assertEqual(evt["event_type"], "STRATEGY_SIGNAL")
        self.assertEqual(evt["symbol"], "BTCUSDT")
        self.assertEqual(evt["timeframe"], "15m")
        self.assertEqual(evt["cell_id"], "BTCUSDT|15m|p1")
        self.assertEqual(evt["signal"], "OPEN_LONG")
        self.assertEqual(evt["reason"], "TEST_REASON")
        self.assertEqual(evt["passed_filters"], True)
        self.assertEqual(evt["in_card_window"], True)
        
        # Check robust flatten behavior (no nested 'details' dict if flattened)
        # Current implementation likely flattens 'details' kwarg into root.
        # But wait, `MatrixEvent.to_dict()` logic was updated to flatten.
        # The sink usually stores the dict form.
        
        # Ensure timestamp is present
        self.assertIn("ts", evt)
        self.assertIn("bar_close_ts", evt)

if __name__ == '__main__':
    unittest.main()
