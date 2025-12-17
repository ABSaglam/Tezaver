# Test Account Page and Reconcile
"""Unit tests for account page and reconcile logic."""

import unittest
from tezaver.ui.subpages.account_page import (
    AccountSnapshot,
    reconcile_account,
    get_gateway,
    get_position_summary,
)


class TestAccountReconcile(unittest.TestCase):
    """Tests for reconcile logic."""
    
    def test_no_creds_graceful_degrade(self):
        """No credentials should return DummyExchangeGateway, no crash."""
        gw = get_gateway()
        # Should not crash and return some gateway
        self.assertIsNotNone(gw)
        
        # get_position_summary should not crash
        summary = get_position_summary()
        self.assertIn("count", summary)
        self.assertIn("notional", summary)
        self.assertIn("unrealized_pnl", summary)
    
    def test_snapshot_mismatch_warn(self):
        """Position mismatch should return WARN or BLOCK."""
        snapshot = AccountSnapshot(
            equity=1000.0,
            positions=[{"symbol": "BTCUSDT", "position_qty": 0.1, "unrealized_pnl": 10.0}],
        )
        # Internal says flat, exchange has position
        internal_positions = {}
        
        result = reconcile_account(snapshot, internal_positions)
        
        # Should be WARN (unexpected exchange position)
        self.assertIn(result["state"], ["WARN", "BLOCK"])
        self.assertIsNotNone(result["reason"])
    
    def test_snapshot_mismatch_internal_vs_exchange(self):
        """Internal has pos but exchange doesn't -> BLOCK."""
        snapshot = AccountSnapshot(
            equity=1000.0,
            positions=[],  # Exchange is flat
        )
        # Internal says we have position
        internal_positions = {"BTCUSDT": 0.1}
        
        result = reconcile_account(snapshot, internal_positions)
        
        # Should be BLOCK (internal thinks we have pos, exchange says flat)
        self.assertEqual(result["state"], "BLOCK")
    
    def test_snapshot_ok_pass(self):
        """Matching internal and exchange should return PASS."""
        snapshot = AccountSnapshot(
            equity=1000.0,
            positions=[{"symbol": "BTCUSDT", "position_qty": 0.1, "unrealized_pnl": 10.0}],
        )
        # Internal matches exchange
        internal_positions = {"BTCUSDT": 0.1}
        
        result = reconcile_account(snapshot, internal_positions)
        
        # Should be PASS
        self.assertEqual(result["state"], "PASS")
    
    def test_snapshot_with_error_returns_unknown(self):
        """Snapshot with error should return UNKNOWN."""
        snapshot = AccountSnapshot(
            error="Connection failed"
        )
        
        result = reconcile_account(snapshot, {})
        
        # Should be UNKNOWN
        self.assertEqual(result["state"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
