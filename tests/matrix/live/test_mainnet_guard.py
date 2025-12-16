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


if __name__ == "__main__":
    unittest.main()
