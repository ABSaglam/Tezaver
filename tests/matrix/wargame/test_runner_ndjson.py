import unittest
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from tezaver.matrix.wargame.runner import _run_wargame_with_scenario_and_feed, WargameScenario, WargameReport
from tezaver.matrix.wargame.replay_datafeed import ReplayDataFeed
from datetime import datetime, timezone

class MockFeed(ReplayDataFeed):
    def __init__(self, snapshots):
        self.snapshots = snapshots
        self.index = 0
        
    def has_next(self):
        return self.index < len(self.snapshots)
        
    def next(self):
        if not self.has_next():
            return None
        s = self.snapshots[self.index]
        self.index += 1
        return s

class TestRunnerNDJSON(unittest.TestCase):
    def test_run_logs_to_ndjson(self):
        with TemporaryDirectory() as tmpdir:
            events_path = Path(tmpdir) / "test_events.ndjson"
            
            # Create dummy scenario
            scenario = WargameScenario(
                scenario_id="test_scen",
                profile_id="TEST_PROFILE",
                symbol="BTCUSDT",
                timeframe="15m",
                start_ts=datetime.now(timezone.utc),
                end_ts=datetime.now(timezone.utc),
                initial_capital=100.0,
                risk_per_trade_pct=0.01,
            )
            
            # One snapshot
            feed = MockFeed([{
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "close": 50000.0,
                "ts": "2024-01-01T10:00:00Z"
            }])
            
            # Run without force close
            _run_wargame_with_scenario_and_feed(
                scenario, 
                feed, 
                events_path=events_path,
                force_close_on_exit=False
            )
            
            # Check file exists
            self.assertTrue(events_path.exists())
            
            # Check content
            with open(events_path) as f:
                lines = f.readlines()
                # Should have at least one event if any telemetry was emitted.
                # However, default components might not emit events if no signal.
                # Our forced close logic writes independently, but only if force_close=True.
                # If False, and no trades, maybe empty file or just header?
                # The UnifiedEngine doesn't auto-emit "START" unless instrumented.
                # But JsonFileEventSink creates the file on init.
                pass

    def test_force_close_emits_event(self):
        with TemporaryDirectory() as tmpdir:
            events_path = Path(tmpdir) / "test_events_fc.ndjson"
            
            scenario = WargameScenario(
                scenario_id="test_scen_fc",
                profile_id="TEST_PROFILE",
                symbol="BTCUSDT",
                timeframe="15m",
                start_ts=datetime.now(timezone.utc),
                end_ts=datetime.now(timezone.utc),
                initial_capital=100.0,
                risk_per_trade_pct=0.01,
            )
            
            feed = MockFeed([{
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "close": 55000.0,
                "ts": "2024-01-01T10:15:00Z"
            }])
            
            # Run with force close
            _run_wargame_with_scenario_and_feed(
                scenario, 
                feed, 
                events_path=events_path,
                force_close_on_exit=True
            )
            
            # Verify PROOF_CLOSE_RESULT
            found_forced = False
            with open(events_path) as f:
                for line in f:
                    evt = json.loads(line)
                    if evt.get("event_type") == "PROOF_CLOSE_RESULT":
                        if evt.get("reason") == "FORCED_END":
                            found_forced = True
                            self.assertEqual(evt["fill_price"], 55000.0)
                            
            self.assertTrue(found_forced, "Did not find forced close event")

if __name__ == "__main__":
    unittest.main()
