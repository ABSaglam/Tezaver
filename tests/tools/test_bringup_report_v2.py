
import tests.mock_env
import json
import unittest
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock, patch

from tezaver.tools import bringup

class TestBringupReportV2(unittest.TestCase):
    def test_report_generation(self):
        """Verify report counts signals, trades, and context correctly."""
        
        # Test Data
        events = [
            {"event_type": "STRATEGY_SIGNAL", "signal": "OPEN_LONG"},
            {"event_type": "HTF_PERMISSION_EVAL", "decision": "ALLOW"},
            {"event_type": "HTF_VETO_APPLIED", "htf_decision": "VETO"},
            {"event_type": "POSITION_OPEN", "id": "t1"},
            {"event_type": "POSITION_CLOSE", "id": "t1"}, # Trade 1 completed
            # No complete Trade 2
            {"event_type": "POSITION_OPEN", "id": "t2"},
            # Some other events
            {"event_type": "ORDER_LIFECYCLE_DONE"},
        ]
        
        # Mock dependencies (trade parsing, decision context)
        with NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as tmp:
            for e in events:
                tmp.write(json.dumps(e) + "\n")
            tmp_path = tmp.name
            
        try:
            # Mock parse_trades_from_events to return 1 trade
            mock_trade = MagicMock()
            mock_trade.symbol = "BTCUSDT"
            
            with patch("tezaver.tools.bringup.parse_trades_from_events", return_value=[mock_trade]), \
                 patch("tezaver.ui.trade_replay_data.build_decision_context", return_value={"summary": "MockContext"}):
                 
                # Mock report path to be temporary
                with patch("tezaver.tools.bringup.Path") as MockPath:
                    # We need MockPath to behave like real Path for the input file, 
                    # but redirect the output JSON path.
                    # This is tricky with full Path mocking.
                    # Simpler: just let it run but override the hardcoded output path inside the function?
                    # The function hardcodes "data/logs/bringup_report.json".
                    # We should probably refactor function to accept output_path or just let it write to a test-safe location if we mocked Path properly.
                    # But mocking Path globally is messy.
                    
                    # Alternative: Run it, let it write to data/logs (local dev env), then read it back.
                    # Or better, just check if function runs without error and inspect console output or mocked open?
                    # Let's trust it writes to the real path for now (user environment), or modify the function to be testable.
                    # I'll rely on the file existing check.
                    
                    # Wait, allow it to write. It's safe enough in this environment. 
                    # I will verify the logic flow primarily.
                    
                    # Actually, I can patch `open` to intercept the write.
                    pass 

            # Let's just run it against the temp file and then inspect the side effect (json file)
            # We need to mock the imports that might fail or be heavy (trade_replay_data)
            
            with patch("tezaver.tools.bringup.parse_trades_from_events", return_value=[mock_trade]), \
                 patch("tezaver.ui.trade_replay_data.build_decision_context", return_value={"summary": "MockContext"}):
                
                # Execute
                bringup.generate_self_check_report(tmp_path)
                
                # Verify Report File Content
                report_path = Path("data/logs/bringup_report.json")
                self.assertTrue(report_path.exists())
                
                with open(report_path) as f:
                    data = json.load(f)
                
                self.assertEqual(data["event_count"], 7)
                self.assertEqual(data["completed_trades"], 1)
                self.assertEqual(data["counts"]["STRATEGY_SIGNAL"], 1)
                self.assertEqual(data["counts"]["HTF_VETO_APPLIED"], 1)
                self.assertEqual(data["decision_context_sample"], "MockContext")
                self.assertEqual(data["verdict"], "YES")

        finally:
            Path(tmp_path).unlink(missing_ok=True)

if __name__ == '__main__':
    unittest.main()
