"""
Tests for Preflight Mode (v1)
"""

import unittest
import shutil
import tempfile
import sys
import subprocess
import json
from pathlib import Path
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from tezaver.matrix.live.preflight import (
    run_preflight,
    PreflightContext,
    CheckResult,
    PASS, WARN, BLOCK,
    check_config_sanity,
    check_telemetry_writable,
    check_card_availability,
    check_disk_free
)

@dataclass
class MockConfig:
    poll_interval_sec: float = 5.0
    tick_policy: str = "ON_CLOSED_BAR"
    max_runtime_sec: float = 60.0
    dry_run: bool = True

class TestPreflightUnit(unittest.TestCase):
    
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.telemetry = Path(self.tmp_dir) / "events.ndjson"
        
        self.mock_args = MagicMock()
        self.mock_args.exchange_mode = "DRY_RUN"
        self.mock_args.exchange_enabled = False
        self.mock_args.open_rule_mode = "ALWAYS_OFF"
        
        self.ctx = PreflightContext(
            args=self.mock_args,
            config=MockConfig(),
            symbols=["BTCUSDT"],
            timeframe="15m",
            telemetry_path=self.telemetry
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir)

    def test_config_sanity(self):
        # Valid
        res = check_config_sanity(self.ctx)
        self.assertEqual(res.status, PASS)
        
        # Invalid poll
        self.ctx.config.poll_interval_sec = 0
        res = check_config_sanity(self.ctx)
        self.assertEqual(res.status, BLOCK)

    def test_telemetry_writable(self):
        # Writable
        res = check_telemetry_writable(self.ctx)
        self.assertEqual(res.status, PASS)
        self.assertTrue(self.telemetry.exists())
        
        # Not writable (directory behaves as file)
        bad_path = Path(self.tmp_dir) / "bad" / "file.ndjson"
        # make parent a file to cause error
        with open(Path(self.tmp_dir) / "bad", "w") as f:
            f.write("x")
        
        self.ctx.telemetry_path = bad_path
        res = check_telemetry_writable(self.ctx)
        self.assertEqual(res.status, BLOCK)

    def test_card_availability_skip(self):
        self.ctx.args.open_rule_mode = "ALWAYS_OFF"
        res = check_card_availability(self.ctx)
        self.assertEqual(res.status, PASS)

    def test_card_availability_missing(self):
        self.ctx.args.open_rule_mode = "CARD_STRICT_WINDOW"
        # We are in tmp dir, so card path "data/coin_profiles..." won't verify well relative to CWD
        # The function uses relative path "data/..." so we need to mock Path.exists
        
        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False
            res = check_card_availability(self.ctx)
            self.assertEqual(res.status, BLOCK)
            self.assertIn("Missing cards", res.message)

    @patch("tezaver.matrix.live.preflight.shutil.disk_usage")
    def test_disk_free(self, mock_usage):
        # 1 GB free
        mock_usage.return_value = (1000, 500, 1024 * 1024 * 1024)
        res = check_disk_free(self.ctx)
        self.assertEqual(res.status, PASS)
        
        # 100 MB free
        mock_usage.return_value = (1000, 500, 100 * 1024 * 1024)
        res = check_disk_free(self.ctx)
        self.assertEqual(res.status, WARN)

    def test_run_preflight_telemetry(self):
        # Run full preflight
        res = run_preflight(self.ctx, enforce_mode="BLOCK")
        self.assertIn(res.decision, [PASS, WARN]) # system tests usually pass in env
        
        # Check telemetry emitted
        with open(self.telemetry, "r") as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 1)
        event = json.loads(lines[0])
        self.assertEqual(event["event_type"], "PREFLIGHT_EVAL")
        self.assertEqual(event["scope"], "GLOBAL")


class TestPreflightIntegration(unittest.TestCase):
    
    def test_preflight_block_exit(self):
        """Test that BLOCK decision causes exit code 2."""
        # Use a fake symbol and CARD mode to force missing card -> BLOCK
        cmd = [
            sys.executable, "-m", "tezaver.matrix.live.live_loop",
            "run",
            "--preflight",
            "--preflight-enforce", "BLOCK",
            "--symbols", "FAKE_SYMBOL_XYZ",
            "--open-rule-mode", "CARD_STRICT_WINDOW",
            "--runtime", "1"
        ]
        
        env = {"PYTHONPATH": "src"}
        
        # Run process
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        # Expect exit code 2
        self.assertEqual(result.returncode, 2, f"Params: {cmd}\nOutput: {result.stdout}\nStderr: {result.stderr}")
        self.assertIn("BLOCK EXIT", result.stdout)
        self.assertIn("card_availability", result.stdout)

    def test_preflight_pass_continues(self):
        """Test that PASS/WARN continues to loop."""
        # Standard run, should PASS config
        cmd = [
            sys.executable, "-m", "tezaver.matrix.live.live_loop",
            "run",
            "--preflight",
            "--runtime", "1",
            "--poll", "1"
        ]
        
        env = {"PYTHONPATH": "src"}
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        # Exit code 0 (success finished runtime)
        self.assertEqual(result.returncode, 0, f"Output: {result.stdout}")
        self.assertIn("Preflight finished", result.stdout)
        self.assertIn("Finished: polls=", result.stdout)

if __name__ == "__main__":
    unittest.main()
