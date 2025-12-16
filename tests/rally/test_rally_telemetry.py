
import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import List

from tezaver.matrix.wargame.runner import RallyTelemetryAnalyzer
from tezaver.matrix.core.telemetry import MatrixEventType, MatrixEvent, InMemoryEventSink
from tezaver.rally.rally_detector_v2 import detect_rallies_v2_micro_booster

# Mock inner analyzer
class MockAnalyzer:
    def analyze(self, snapshot):
        return []

class TestRallyTelemetry(unittest.TestCase):
    def test_rally_detector_v2_schema(self):
        """Verify detector output has required columns."""
        # Create synthetic 15m data with a rally
        dates = pd.date_range("2024-01-01", periods=50, freq="15min")
        df = pd.DataFrame({
            "timestamp": dates,
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 1000.0,
            "vol_rel": 1.0, # default
        })
        
        # Inject ignition
        df.loc[10:12, "close"] = 99.0 # ignition window
        
        # Inject spike anchor
        df.loc[14, "vol_rel"] = 3.0
        df.loc[14, "vol_spike"] = True
        
        # Inject rally peak
        df.loc[20, "close"] = 110.0 # >5.5% gain
        
        events = detect_rallies_v2_micro_booster(df, deduplicate=False)
        
        self.assertFalse(events.empty)
        cols = list(events.columns)
        expected = ["event_time", "future_max_gain_pct", "bars_to_peak"]
        for c in expected:
            self.assertIn(c, cols)
            
        print("V2 Output Schema Validated:", cols)

    def test_telemetry_analyzer_emits_event(self):
        """Verify RallyTelemetryAnalyzer emits RALLY_DETECTED."""
        sink = InMemoryEventSink()
        inner_analyzer = MockAnalyzer()
        
        # Setup fake rally data
        ts = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        rally_data = {
            "event_time": ts,
            "bars_to_peak": 5,
            "future_max_gain_pct": 0.10
        }
        
        # Map timestamp string because runner logic converts
        # Wait, runner logic uses exact timestamp object match if present?
        # Runner logic: if ts in rallies_by_ts (where keys are datetime)
        rallies_by_ts = {
            ts: [rally_data]
        }
        
        analyzer = RallyTelemetryAnalyzer(
            inner=inner_analyzer,
            rallies_by_ts=rallies_by_ts,
            event_sink=sink,
            symbol="TEST"
        )
        
        # Simulate tick
        snapshot = {
            "timestamp": ts,
            "symbol": "TEST",
            "timeframe": "15m"
        }
        
        analyzer.analyze(snapshot)
        
        # Check sink
        events = sink.get_events()
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt.event_type, MatrixEventType.RALLY_DETECTED)
        self.assertEqual(evt.symbol, "TEST")
        # details
        self.assertEqual(evt.details["bars_to_peak"], 5)
        
        print("Telemetry Emitted:", evt)

if __name__ == "__main__":
    unittest.main()
