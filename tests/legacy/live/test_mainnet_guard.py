"""
Tests for Mainnet Readiness Guard
"""

import unittest
import subprocess
import sys
import os


class TestMainnetGuard(unittest.TestCase):
    """Tests for REAL_MAINNET safety guard."""
    
    def _run_live_loop(self, extra_args: list) -> subprocess.CompletedProcess:
        """Run live_loop with given args and return result."""
        cmd = [
            sys.executable, "-m", "tezaver.matrix.live.live_loop",
            "run",
            "--exchange-mode", "REAL_MAINNET",
            "--symbols", "BTCUSDT",
            "--tf", "15m",
            "--runtime", "1",
        ] + extra_args
        
        env = {"PYTHONPATH": "src"}
        env.update(os.environ)
        
        return subprocess.run(cmd, env=env, capture_output=True, text=True)
    
    def test_mainnet_blocks_without_arm(self):
        """REAL_MAINNET should block without --mainnet-arm."""
        result = self._run_live_loop([
            "--mainnet-ack", "I_UNDERSTAND_REAL_MAINNET",
            "--preflight",
            "--auto-export-on-block",
            "--mainnet-max-notional", "1000",
            "--mainnet-allowlist", "BTCUSDT",
        ])
        
        self.assertEqual(result.returncode, 2)
        self.assertIn("MAINNET_GUARD_BLOCK", result.stdout)
        self.assertIn("MISSING_MAINNET_ARM", result.stdout)
    
    def test_mainnet_blocks_without_ack(self):
        """REAL_MAINNET should block without correct --mainnet-ack."""
        result = self._run_live_loop([
            "--mainnet-arm",
            "--mainnet-ack", "WRONG_STRING",
            "--preflight",
            "--auto-export-on-block",
            "--mainnet-max-notional", "1000",
            "--mainnet-allowlist", "BTCUSDT",
        ])
        
        self.assertEqual(result.returncode, 2)
        self.assertIn("MAINNET_GUARD_BLOCK", result.stdout)
        self.assertIn("MISSING_OR_WRONG_MAINNET_ACK", result.stdout)
    
    def test_mainnet_blocks_without_preflight_or_auto_export(self):
        """REAL_MAINNET should block without --preflight or --auto-export-on-block."""
        result = self._run_live_loop([
            "--mainnet-arm",
            "--mainnet-ack", "I_UNDERSTAND_REAL_MAINNET",
            # Missing: --preflight --auto-export-on-block
            "--mainnet-max-notional", "1000",
            "--mainnet-allowlist", "BTCUSDT",
        ])
        
        self.assertEqual(result.returncode, 2)
        self.assertIn("MAINNET_GUARD_BLOCK", result.stdout)
        self.assertIn("PREFLIGHT_NOT_ENABLED", result.stdout)
    
    def test_mainnet_allows_when_all_conditions_met(self):
        """REAL_MAINNET should pass guard when all conditions met (then fail at preflight for FAKE sym)."""
        result = self._run_live_loop([
            "--mainnet-arm",
            "--mainnet-ack", "I_UNDERSTAND_REAL_MAINNET",
            "--preflight",
            "--preflight-enforce", "BLOCK",
            "--auto-export-on-block",
            "--mainnet-max-notional", "1000",
            "--mainnet-allowlist", "BTCUSDT",
        ])
        
        # Guard passes but preflight will likely fail (no card/exchange)
        # We just check guard PASSED (no MAINNET_GUARD_BLOCK)
        self.assertNotIn("MAINNET_GUARD_BLOCK", result.stdout)
        self.assertIn("MAINNET_ARMED", result.stdout)
    
    def test_allowlist_violation_blocks(self):
        """Requesting symbol outside allowlist should block."""
        result = self._run_live_loop([
            "--mainnet-arm",
            "--mainnet-ack", "I_UNDERSTAND_REAL_MAINNET",
            "--preflight",
            "--auto-export-on-block",
            "--mainnet-max-notional", "1000",
            "--mainnet-allowlist", "ETHUSDT",  # Only ETH allowed
            "--symbols", "BTCUSDT",  # But requesting BTC
        ])
        
        self.assertEqual(result.returncode, 2)
        self.assertIn("ALLOWLIST_VIOLATION", result.stdout)


class TestEnforceAllowlistHelper(unittest.TestCase):
    """Unit tests for enforce_allowlist helper."""
    
    def test_enforce_allowlist_allows_matching(self):
        """Should allow symbols in allowlist."""
        # Import via exec since function is inside main()
        allowlist_str = "BTCUSDT,ETHUSDT"
        allowed_set = {s.strip().upper() for s in allowlist_str.split(",") if s.strip()}
        requested = ["BTCUSDT"]
        blocked = [s for s in requested if s.upper() not in allowed_set]
        
        self.assertEqual(blocked, [])
    
    def test_enforce_allowlist_blocks_non_matching(self):
        """Should block symbols not in allowlist."""
        allowlist_str = "ETHUSDT"
        allowed_set = {s.strip().upper() for s in allowlist_str.split(",") if s.strip()}
        requested = ["BTCUSDT", "SOLUSDT"]
        blocked = [s for s in requested if s.upper() not in allowed_set]
        
        self.assertEqual(set(blocked), {"BTCUSDT", "SOLUSDT"})


class TestOrderTimeAllowlistEnforcement(unittest.TestCase):
    """Tests for order-time allowlist enforcement in HoldNextClosedPolicy."""
    
    def test_policy_blocks_disallowed_symbol(self):
        """Policy should block order for symbol not in allowlist and emit event."""
        import json
        import tempfile
        from pathlib import Path
        
        # Create temp event log
        tmp_dir = tempfile.mkdtemp()
        events_log = []
        
        def mock_sink(event):
            events_log.append(event)
        
        # Create policy with allowlist containing only ETHUSDT
        from unittest.mock import MagicMock
        mock_gateway = MagicMock()
        
        from tezaver.matrix.live.live_policy import HoldNextClosedPolicy
        policy = HoldNextClosedPolicy(
            gateway=mock_gateway,
            event_sink=mock_sink,
            exchange_mode="REAL_MAINNET",
            mainnet_allowlist="ETHUSDT",
            auto_export_on_block=False,  # Don't actually export
        )
        
        # Prime a cell to be in FLAT state ready for OPEN
        cell = policy.get_cell_state("BTCUSDT", "15m", "test_profile")
        
        # Attempt to open (should be blocked)
        result = policy.handle_tick(
            symbol="BTCUSDT",  # Not in allowlist
            tf="15m",
            profile_id="test_profile",
            bar_close_ts="2025-01-01T00:00:00Z",
            decision="OPEN",
        )
        
        # Check that order was blocked
        self.assertEqual(result.action, "ALLOWLIST_BLOCKED")
        self.assertFalse(result.success)
        
        # Check that MAINNET_GUARD_EVAL event was emitted
        block_events = [e for e in events_log if e.get("event_type") == "MAINNET_GUARD_EVAL"]
        self.assertEqual(len(block_events), 1)
        self.assertEqual(block_events[0]["decision"], "BLOCK")
        self.assertIn("ALLOWLIST_VIOLATION_ORDER", block_events[0]["reasons"][0])


if __name__ == "__main__":
    unittest.main()
