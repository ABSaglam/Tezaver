
import unittest
from datetime import datetime, timezone
from tezaver.ui.trade_replay_data import extract_rally_events, RallyOverlay

class TestRallyOverlay(unittest.TestCase):
    def test_extract_rally_events_filters_symbol_tf(self):
        """Verify sorting and filtering of rally events."""
        events = [
            # Matching
            {
                "event_type": "RALLY_DETECTED",
                "symbol": "BTC", 
                "timeframe": "15m",
                "bar_close_ts": "2024-01-01T12:00:00+00:00",
                "details": {"future_max_gain_pct": 0.05, "bars_to_peak": 10}
            },
            # Wrong symbol
            {
                "event_type": "RALLY_DETECTED",
                "symbol": "ETH", 
                "timeframe": "15m",
                "bar_close_ts": "2024-01-01T12:00:00+00:00",
                "details": {}
            },
            # Wrong TF
            {
                "event_type": "RALLY_DETECTED",
                "symbol": "BTC", 
                "timeframe": "1h",
                "bar_close_ts": "2024-01-01T12:00:00+00:00",
                "details": {}
            },
             # Wrong Type
            {
                "event_type": "OTHER",
                "symbol": "BTC", 
                "timeframe": "15m",
                "bar_close_ts": "2024-01-01T12:00:00+00:00",
                "details": {}
            }
        ]
        
        rallies = extract_rally_events(
            events,
            "2024-01-01T00:00:00+00:00",
            "2024-01-02T00:00:00+00:00",
            symbol="BTC",
            timeframe="15m"
        )
        
        self.assertEqual(len(rallies), 1)
        self.assertEqual(rallies[0].ts, "2024-01-01T12:00:00+00:00")
        
    def test_label_formatting_gain_pct_and_bars(self):
        """Verify label is formatted correctly."""
        events = [{
            "event_type": "RALLY_DETECTED",
            "bar_close_ts": "2024-01-01T12:00:00+00:00",
            "details": {"future_max_gain_pct": 0.1234, "bars_to_peak": 42}
        }]
        
        rallies = extract_rally_events(events, "2024-01-01T00:00:00+00:00", "2024-01-02T00:00:00+00:00")
        self.assertEqual(len(rallies), 1)
        # "RALLY +12.3% / 42 bars"
        self.assertEqual(rallies[0].label, "RALLY +12.3% / 42 bars")
        self.assertEqual(rallies[0].gain_pct, 0.1234)
        self.assertEqual(rallies[0].bars_to_peak, 42)

    def test_ts_resolution_prefers_bar_close_ts(self):
        """Verify timestamps priority: bar_close_ts > details.event_time > ts"""
        events = [
            {
                "event_type": "RALLY_DETECTED",
                "bar_close_ts": "2024-01-01T10:00:00+00:00",
                "ts": "2024-01-01T11:00:00+00:00",
                "details": {"event_time": "2024-01-01T12:00:00+00:00"}
            },
            {
                "event_type": "RALLY_DETECTED",
                "ts": "2024-01-01T11:00:00+00:00",
                "details": {"event_time": "2024-01-01T12:00:00+00:00"}
            }
        ]
        
        rallies = extract_rally_events(events, "2024-01-01T00:00:00+00:00", "2024-01-02T00:00:00+00:00")
        
        # First one should use bar_close_ts (10:00)
        self.assertEqual(rallies[0].ts, "2024-01-01T10:00:00+00:00")
        # Second one should use details.event_time (12:00)
        self.assertEqual(rallies[1].ts, "2024-01-01T12:00:00+00:00")

if __name__ == "__main__":
    unittest.main()
