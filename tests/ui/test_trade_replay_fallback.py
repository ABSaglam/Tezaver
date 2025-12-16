import unittest
from tezaver.ui.trade_replay_data import build_fallback_candles_from_events

class TestTradeReplayFallback(unittest.TestCase):
    def test_build_fallback_candles_basic(self):
        events = [
            # Relevant signal
            {
                "event_type": "STRATEGY_SIGNAL",
                "ts": "2024-01-01T12:00:00Z",
                "close": 50000.0,
            },
            # Relevant order done
            {
                "event_type": "ORDER_LIFECYCLE_DONE",
                "ts": "2024-01-01T12:15:00Z",
                "fill_price": 50100.0,
            },
            # Irrelevant (no price)
            {
                "event_type": "RISK_CHECK",
                "ts": "2024-01-01T12:10:00Z",
            },
            # Out of window
            {
                "event_type": "STRATEGY_SIGNAL",
                "ts": "2024-01-01T13:00:00Z",
                "close": 50500.0,
            },
        ]
        
        candles = build_fallback_candles_from_events(
            events, 
            start_ts="2024-01-01T12:00:00Z", 
            end_ts="2024-01-01T12:30:00Z"
        )
        
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0]["ts"], "2024-01-01T12:00:00Z")
        self.assertEqual(candles[0]["close"], 50000.0)
        self.assertEqual(candles[0]["open"], 50000.0)
        
        self.assertEqual(candles[1]["ts"], "2024-01-01T12:15:00Z")
        self.assertEqual(candles[1]["close"], 50100.0)

    def test_build_fallback_candles_snapshot_price(self):
        # Test pulling price from snapshot dict inside event
        events = [
            {
                "event_type": "STRATEGY_SIGNAL",
                "ts": "2024-01-02T10:00:00Z",
                "snapshot": {"close": 42000.0}
            }
        ]
        
        candles = build_fallback_candles_from_events(
            events,
            start_ts="2024-01-02T09:00:00Z",
            end_ts="2024-01-02T11:00:00Z"
        )
        
        self.assertEqual(len(candles), 1)
        self.assertEqual(candles[0]["close"], 42000.0)

    def test_fallback_from_proof_open_close(self):
        # Test PROOF_OPEN_RESULT and PROOF_CLOSE_RESULT
        events = [
            {
                "event_type": "PROOF_OPEN_RESULT",
                "ts": "2024-01-01T10:00:00Z",
                "open_px": 30000.0,
                # No fill_price or close_px typical for open result sometimes, but let's say fill_price exists
                "fill_price": 30005.0 
            },
            {
                "event_type": "PROOF_CLOSE_RESULT",
                "ts": "2024-01-01T10:05:00Z", # ts
                "bar_close_ts": "2024-01-01T10:15:00Z", # preferred
                "fill_price": 31000.0
            }
        ]
        
        candles = build_fallback_candles_from_events(
            events,
            start_ts="2024-01-01T09:00:00Z",
            end_ts="2024-01-01T11:00:00Z"
        )
        
        self.assertEqual(len(candles), 2)
        # Point 1: PROOF_OPEN fallback to fill_price
        self.assertEqual(candles[0]["ts"], "2024-01-01T10:00:00Z")
        self.assertEqual(candles[0]["close"], 30005.0)
        
        # Point 2: PROOF_CLOSE uses bar_close_ts
        self.assertEqual(candles[1]["ts"], "2024-01-01T10:15:00Z")
        self.assertEqual(candles[1]["close"], 31000.0)

    def test_fallback_insufficient_points_message(self):
        # Only 1 point, so UI should complain (we test function returns 1, UI test logic separate)
        events = [
            {
                "event_type": "PROOF_OPEN_RESULT",
                "ts": "2024-01-01T10:00:00Z",
                "fill_price": 30000.0
            }
        ]
        candles = build_fallback_candles_from_events(
            events,
            start_ts="2024-01-01T09:00:00Z",
            end_ts="2024-01-01T11:00:00Z"
        )
        self.assertEqual(len(candles), 1)
        # This confirms logic: we get 1 candle, UI layer decides < 2 check.


    def test_fallback_from_strategy_signals(self):
        # Test STRATEGY_SIGNAL close and snapshot.close
        events = [
            {
                "event_type": "STRATEGY_SIGNAL",
                "ts": "2024-01-01T12:00:00Z",
                "close": 100.0,
            },
            {
                "event_type": "STRATEGY_SIGNAL",
                "ts": "2024-01-01T12:05:00Z",
                "snapshot": {"close": 101.0}
            }
        ]
        candles = build_fallback_candles_from_events(
            events,
            start_ts="2024-01-01T11:59:00Z",
            end_ts="2024-01-01T12:06:00Z"
        )
        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0]["close"], 100.0)
        self.assertEqual(candles[1]["close"], 101.0)

    def test_parse_open_trades(self):
        from tezaver.ui.trade_replay_data import parse_open_trades_from_events
        events = [
            # Open
            {
                "event_type": "PROOF_OPEN_RESULT",
                "symbol": "BTC",
                "timeframe": "1h",
                "ts": "2024-01-01T10:00:00Z",
                "fill_price": 50000.0,
                "open_qty": 1.0,
            },
            # Close (completes it)
            {
                "event_type": "PROOF_CLOSE_RESULT",
                "symbol": "BTC",
                "timeframe": "1h",
                "ts": "2024-01-01T11:00:00Z",
                "fill_price": 51000.0,
            },
            # Another Open (remains open)
            {
                "event_type": "PROOF_OPEN_RESULT",
                "symbol": "ETH",
                "timeframe": "1h",
                "ts": "2024-01-01T12:00:00Z",
                "fill_price": 3000.0,
                "open_qty": 10.0,
            }
        ]
        
        # parse_open_trades should ONLY return ETH
        opens = parse_open_trades_from_events(events)
        self.assertEqual(len(opens), 1)
        self.assertEqual(opens[0].symbol, "ETH")
        self.assertEqual(opens[0].open_px, 3000.0)
        self.assertIsNone(opens[0].close_ts)

if __name__ == "__main__":
    unittest.main()

