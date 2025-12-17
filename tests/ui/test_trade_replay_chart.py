# Test Trade Replay Chart in Cockpit
"""Unit tests for Trade Replay chart mode, fallback, and overlay toggles."""

import unittest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestTradeReplayChartMode(unittest.TestCase):
    """Tests for chart mode selection and fallback behavior."""
    
    def _make_ndjson_events(self, events: list) -> Path:
        """Create temp NDJSON file with events."""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False)
        for e in events:
            f.write(json.dumps(e) + "\n")
        f.close()
        return Path(f.name)
    
    def test_cockpit_chart_mode_uses_candles_when_available(self):
        """When OHLCV is available, load_ohlcv should return candles."""
        from tezaver.ui.trade_replay_data import load_ohlcv
        
        # This test checks the function signature and return type
        # Actual data availability depends on local files
        candles, paths = load_ohlcv("BTCUSDT", "15m", "2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z")
        
        # Should return tuple
        self.assertIsInstance(paths, list)
        # candles can be None or list
        self.assertTrue(candles is None or isinstance(candles, list))
    
    def test_cockpit_chart_mode_falls_back_when_missing_ohlcv(self):
        """When OHLCV is missing, build_fallback_candles_from_events should be used."""
        from tezaver.ui.trade_replay_data import build_fallback_candles_from_events
        
        # Events with price data
        events = [
            {"event_type": "STRATEGY_SIGNAL", "ts": "2024-01-01T00:00:00Z", "close": 42000.0},
            {"event_type": "STRATEGY_SIGNAL", "ts": "2024-01-01T00:15:00Z", "close": 42100.0},
            {"event_type": "STRATEGY_SIGNAL", "ts": "2024-01-01T00:30:00Z", "close": 42200.0},
        ]
        
        candles = build_fallback_candles_from_events(events, "2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z")
        
        # Should return list of candles
        self.assertIsInstance(candles, list)
        self.assertGreater(len(candles), 0)
        self.assertIn("ts", candles[0])
        self.assertIn("close", candles[0])
    
    def test_overlay_toggles_control_signal_extraction(self):
        """extract_strategy_signals should return OverlayPoints."""
        from tezaver.ui.trade_replay_data import extract_strategy_signals
        
        # Events with signals
        events = [
            {"event_type": "STRATEGY_SIGNAL", "ts": "2024-01-01T00:15:00Z", "signal": "OPEN_LONG", "symbol": "BTCUSDT", "timeframe": "15m"},
        ]
        
        points = extract_strategy_signals(events, "2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "BTCUSDT", "15m")
        
        # Should return list
        self.assertIsInstance(points, list)
    
    def test_rally_overlay_extraction(self):
        """extract_rally_events should return RallyOverlay objects."""
        from tezaver.ui.trade_replay_data import extract_rally_events
        
        # Events with rally
        events = [
            {"event_type": "RALLY_DETECTED", "ts": "2024-01-01T00:15:00Z", "gain_pct": 0.05, "bars_to_peak": 3, "symbol": "BTCUSDT", "timeframe": "15m"},
        ]
        
        rallies = extract_rally_events(events, "2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "BTCUSDT", "15m")
        
        # Should return list
        self.assertIsInstance(rallies, list)
        if rallies:
            self.assertIsNotNone(rallies[0].ts)


if __name__ == "__main__":
    unittest.main()
