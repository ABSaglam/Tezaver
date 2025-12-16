"""
Tests for Trade Replay Data Helpers
"""

import unittest
from datetime import datetime, timezone


class TestTradeReplayData(unittest.TestCase):
    """Unit tests for trade replay data parsing."""
    
    def test_parse_trades_pairs_open_close(self):
        """Should pair ORDER_LIFECYCLE_DONE OPEN/CLOSE events into trades."""
        from tezaver.ui.trade_replay_data import parse_trades_from_events
        
        events = [
            {
                "event_type": "ORDER_LIFECYCLE_DONE",
                "action": "OPEN",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "ts": "2025-01-01T10:00:00Z",
                "fill_price": 42000.0,
                "fill_qty": 0.01,
                "side": "BUY",
            },
            {
                "event_type": "ORDER_LIFECYCLE_DONE",
                "action": "CLOSE",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "ts": "2025-01-01T10:30:00Z",
                "fill_price": 42500.0,
                "fill_qty": 0.01,
                "reason": "NEXT_SIGNAL",
            },
        ]
        
        trades = parse_trades_from_events(events)
        
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].symbol, "BTCUSDT")
        self.assertEqual(trades[0].timeframe, "15m")
        self.assertEqual(trades[0].open_px, 42000.0)
        self.assertEqual(trades[0].close_px, 42500.0)
        self.assertEqual(trades[0].side, "BUY")
        self.assertAlmostEqual(trades[0].net_pnl, 5.0, places=2)  # (42500-42000)*0.01
    
    def test_timeline_filters_window(self):
        """Timeline should filter events within trade window."""
        from tezaver.ui.trade_replay_data import build_trade_timeline, Trade
        
        trade = Trade(
            trade_id="test",
            symbol="BTCUSDT",
            timeframe="15m",
            open_ts="2025-01-01T10:00:00+00:00",
            close_ts="2025-01-01T10:30:00+00:00",
            open_px=42000,
            close_px=42500,
            side="BUY",
            qty=0.01,
            net_pnl=5.0,
            close_reason="SIGNAL",
        )
        
        events = [
            {"event_type": "PREFLIGHT_EVAL", "ts": "2025-01-01T09:45:00+00:00", "symbol": "BTCUSDT", "timeframe": "15m", "decision": "PASS"},
            {"event_type": "ORDER_LIFECYCLE_START", "ts": "2025-01-01T10:00:00+00:00", "symbol": "BTCUSDT", "timeframe": "15m"},
            {"event_type": "ROUTER_TICK", "ts": "2025-01-01T12:00:00+00:00", "symbol": "BTCUSDT"},  # Outside window
        ]
        
        timeline = build_trade_timeline(events, trade, window_minutes=30)
        
        # Should include events within window (first 2), exclude last one
        self.assertEqual(len(timeline), 2)
        self.assertEqual(timeline[0].event_type, "PREFLIGHT_EVAL")
        self.assertEqual(timeline[1].event_type, "ORDER_LIFECYCLE_START")
    
    def test_handles_missing_fields_gracefully(self):
        """Should handle events with missing fields without crashing."""
        from tezaver.ui.trade_replay_data import parse_trades_from_events, build_trade_timeline, Trade
        
        # Events with minimal/missing fields
        events = [
            {"event_type": "ORDER_LIFECYCLE_DONE", "action": "OPEN"},  # Missing symbol, tf, etc.
            {"event_type": "ORDER_LIFECYCLE_DONE"},  # No action
            {"event_type": "POLICY_CYCLE_RESULT", "symbol": "ETHUSDT"},  # Minimal
        ]
        
        # Should not crash
        trades = parse_trades_from_events(events)
        self.assertIsInstance(trades, list)
        
        # Build timeline with minimal trade
        trade = Trade(
            trade_id="test",
            symbol="ETHUSDT",
            timeframe="15m",
            open_ts="invalid-ts",  # Invalid
            close_ts=None,
            open_px=None,
            close_px=None,
            side="BUY",
            qty=None,
            net_pnl=None,
            close_reason=None,
        )
        
        timeline = build_trade_timeline(events, trade)
        self.assertIsInstance(timeline, list)
    
    def test_filtering_by_symbol_tf(self):
        """filter_trades should filter by symbol and timeframe."""
        from tezaver.ui.trade_replay_data import filter_trades, Trade
        
        trades = [
            Trade("1", "BTCUSDT", "15m", "2025-01-01T10:00:00Z", 42000, "2025-01-01T10:30:00Z", 42500, "BUY", 0.01, 5.0, "SIG", None, None),
            Trade("2", "ETHUSDT", "15m", "2025-01-01T11:00:00Z", 3000, "2025-01-01T11:30:00Z", 3050, "BUY", 0.1, 5.0, "SIG", None, None),
            Trade("3", "BTCUSDT", "1h", "2025-01-01T12:00:00Z", 42100, "2025-01-01T13:00:00Z", 42200, "BUY", 0.01, 1.0, "SIG", None, None),
        ]
        
        # Filter by symbol
        btc_only = filter_trades(trades, symbol="BTCUSDT")
        self.assertEqual(len(btc_only), 2)
        
        # Filter by timeframe
        tf_15m = filter_trades(trades, timeframe="15m")
        self.assertEqual(len(tf_15m), 2)
        
        # Filter by both
        btc_15m = filter_trades(trades, symbol="BTCUSDT", timeframe="15m")
        self.assertEqual(len(btc_15m), 1)
        
        # ALL filter
        all_trades = filter_trades(trades, symbol="ALL", timeframe="ALL")
        self.assertEqual(len(all_trades), 3)
    
    def test_sl_tp_extraction_optional(self):
        """SL/TP fields should be extracted when present."""
        from tezaver.ui.trade_replay_data import parse_trades_from_events
        
        events = [
            {
                "event_type": "ORDER_LIFECYCLE_DONE",
                "action": "OPEN",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "ts": "2025-01-01T10:00:00Z",
                "fill_price": 42000.0,
                "fill_qty": 0.01,
                "side": "BUY",
                "stop_price": 41500.0,  # SL field
                "take_profit": 43000.0,  # TP field
            },
            {
                "event_type": "ORDER_LIFECYCLE_DONE",
                "action": "CLOSE",
                "symbol": "BTCUSDT",
                "timeframe": "15m",
                "ts": "2025-01-01T10:30:00Z",
                "fill_price": 42500.0,
            },
        ]
        
        trades = parse_trades_from_events(events)
        
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].sl_px, 41500.0)
        self.assertEqual(trades[0].tp_px, 43000.0)
    
    def test_ohlcv_path_fallback_list(self):
        """get_ohlcv_paths should return list of paths to try."""
        from tezaver.ui.trade_replay_data import get_ohlcv_paths
        
        paths = get_ohlcv_paths("BTCUSDT", "15m")
        
        # Should return at least 2 paths
        self.assertGreaterEqual(len(paths), 2)
        
        # First path should be primary coin_cells path
        self.assertIn("coin_cells", str(paths[0]))
        self.assertIn("history_15m", str(paths[0]))

if __name__ == "__main__":
    unittest.main()
