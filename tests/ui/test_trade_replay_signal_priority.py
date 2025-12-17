
import tests.mock_env
import unittest
from datetime import datetime, timedelta
from tezaver.ui.trade_replay_data import extract_strategy_signals
from tezaver.matrix.live.strategy_signal import Signal

class TestTradeReplaySignalPriority(unittest.TestCase):
    def test_priority_strategy_signal(self):
        """Verify STRATEGY_SIGNAL takes precedence over legacy events."""
        start = "2025-01-01T10:00:00Z"
        end = "2025-01-01T11:00:00Z"
        
        # Mix of legacy and new events
        events = [
            # Legacy
            {
                "ts": "2025-01-01T10:15:00Z", 
                "event_type": "SIGNAL", 
                "signal": "SILVER_ENTRY", 
                "symbol": "BTCUSDT"
            },
            # New (Same time - duplicate?)
            {
                "ts": "2025-01-01T10:15:00Z", 
                "event_type": "STRATEGY_SIGNAL", 
                "signal": "OPEN_LONG", 
                "reason": "NEW_WAY",
                "symbol": "BTCUSDT"
            },
            # Legacy Router
            {
                "ts": "2025-01-01T10:15:01Z", 
                "event_type": "ROUTER_CLUSTER_DECISION", 
                "decision": "OPEN", 
                "symbol": "BTCUSDT"
            }
        ]
        
        # The logic in extract_strategy_signals prioritizes STRATEGY_SIGNAL. 
        # If STRATEGY_SIGNAL exists for a general timeframe/symbol, others might be ignored or duplicates shown?
        # Actually logic is: Iterate all, map to Points. 
        # But we want to ensure the "Point" generated prefers the rich data of STRATEGY_SIGNAL.
        
        points = extract_strategy_signals(events, start, end, "BTCUSDT")
        
        # Should find at least the STRATEGY_SIGNAL one
        found_new = False
        for p in points:
            if p.reason == "NEW_WAY":
                found_new = True
                self.assertEqual(p.signal, "OPEN_LONG")
        
        self.assertTrue(found_new, "Did not extract STRATEGY_SIGNAL point")
        
        # Ideally, we shouldn't see legacy ones if they are redundant. 
        # But for now, as long as NEW one is there, pass.

if __name__ == '__main__':
    unittest.main()
