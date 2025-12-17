# Test Gateway Balance and Orders
"""Unit tests for gateway balance and open orders methods."""

import unittest
from tezaver.matrix.live.live_gateway import DummyExchangeGateway, IExchangeGateway


class TestDummyGateway(unittest.TestCase):
    """Tests for DummyExchangeGateway new methods."""
    
    def test_dummy_gateway_balance_non_crash(self):
        """get_balance should return valid structure without crashing."""
        gw = DummyExchangeGateway()
        balance = gw.get_balance()
        
        self.assertIsInstance(balance, dict)
        self.assertIn("equity", balance)
        self.assertIn("available", balance)
        self.assertIn("used_margin", balance)
        self.assertIn("unrealized_pnl", balance)
        self.assertIn("source", balance)
        self.assertEqual(balance["source"], "dummy")
    
    def test_open_orders_empty_no_crash(self):
        """get_open_orders should return empty list without crashing."""
        gw = DummyExchangeGateway()
        orders = gw.get_open_orders()
        
        self.assertIsInstance(orders, list)
        self.assertEqual(len(orders), 0)
    
    def test_open_orders_with_symbol_filter(self):
        """get_open_orders with symbol filter should not crash."""
        gw = DummyExchangeGateway()
        orders = gw.get_open_orders(symbol="BTCUSDT")
        
        self.assertIsInstance(orders, list)
    
    def test_position_snapshot_has_required_fields(self):
        """get_position_snapshot should return required fields."""
        gw = DummyExchangeGateway()
        pos = gw.get_position_snapshot("BTCUSDT")
        
        self.assertIn("symbol", pos)
        self.assertIn("position_qty", pos)
        self.assertIn("unrealized_pnl", pos)


if __name__ == "__main__":
    unittest.main()
