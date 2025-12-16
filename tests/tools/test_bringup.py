
import unittest
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

# Assuming structure allows import. We might need to adjust path or mock modules that require imports.
# We will mock load_ohlcv and parse_trades_from_events to test the report generator logic in isolation.

from tezaver.tools.bringup import generate_self_check_report

class TestBringupTool(unittest.TestCase):
    def setUp(self):
        self.test_file = "test_events.ndjson"
        
    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    @patch("tezaver.tools.bringup.parse_trades_from_events")
    @patch("tezaver.tools.bringup.load_ohlcv")
    def test_self_check_with_completed_trades(self, mock_load, mock_parse):
        # Setup mock data
        with open(self.test_file, "w") as f:
            f.write(json.dumps({"event_type": "PROOF_OPEN_RESULT", "symbol": "BTC", "ts": "2024-01-01T00:00:00Z"}) + "\n")
            f.write(json.dumps({"event_type": "PROOF_CLOSE_RESULT", "symbol": "BTC", "ts": "2024-01-01T01:00:00Z"}) + "\n")
            
        # Mock returns
        mock_trade = MagicMock()
        mock_trade.symbol = "BTC"
        mock_trade.timeframe = "15m"
        mock_trade.open_ts = "2024-01-01T00:00:00Z"
        mock_trade.close_ts = "2024-01-01T01:00:00Z"
        
        mock_parse.return_value = [mock_trade]
        mock_load.return_value = (["candle"], []) # Candles found
        
        # Capture output (simple print capture not easily done with unittest alone without custom runner or redirect_stdout)
        # We'll just run it to ensure no exceptions and rely on mocks being called.
        
        with patch("sys.stdout") as mock_stdout:
            generate_self_check_report(self.test_file)
            
            # Check mocks called
            mock_parse.assert_called_once()
            mock_load.assert_called_once()

    @patch("tezaver.tools.bringup.parse_trades_from_events")
    @patch("tezaver.tools.bringup.load_ohlcv")
    def test_self_check_fallback_mode(self, mock_load, mock_parse):
        # Setup mock data
        with open(self.test_file, "w") as f:
             f.write(json.dumps({"event_type": "PROOF_OPEN_RESULT"}) + "\n")
        
        mock_trade = MagicMock()
        mock_trade.symbol = "BTC"
        mock_parse.return_value = [mock_trade]
        mock_load.return_value = (None, []) # No candles
        
        with patch("sys.stdout") as mock_stdout:
            generate_self_check_report(self.test_file)
            mock_load.assert_called_once()
            
if __name__ == "__main__":
    unittest.main()
