# Live Gateway and RealExecutor Tests
"""
Tests for exchange gateway interface and real executor.
"""

import pytest

from tezaver.matrix.live.live_gateway import (
    DummyExchangeGateway,
    ExchangeOrderRequest,
    OrderSide,
)
from tezaver.matrix.core.execution import RealExecutor, RealExecutorConfig


class TestDummyExchangeGateway:
    """Tests for DummyExchangeGateway."""
    
    def test_place_order_succeeds(self):
        """place_order should always succeed with DummyExchangeGateway."""
        gw = DummyExchangeGateway()
        req = ExchangeOrderRequest(symbol="BTCUSDT", side=OrderSide.BUY, quantity=1.0)
        res = gw.place_order(req)
        
        assert res.success is True
        assert res.filled_qty == 1.0
        assert res.avg_price is not None
        assert res.order_id == "DUMMY-ORDER"
    
    def test_place_order_with_price(self):
        """place_order should use provided price."""
        gw = DummyExchangeGateway()
        req = ExchangeOrderRequest(
            symbol="ETHUSDT",
            side=OrderSide.SELL,
            quantity=2.0,
            price=2500.0,
        )
        res = gw.place_order(req)
        
        assert res.success is True
        assert res.avg_price == 2500.0
    
    def test_get_position_snapshot(self):
        """get_position_snapshot should return empty position."""
        gw = DummyExchangeGateway()
        snapshot = gw.get_position_snapshot("BTCUSDT")
        
        assert snapshot["symbol"] == "BTCUSDT"
        assert snapshot["position_qty"] == 0.0


class TestRealExecutor:
    """Tests for RealExecutor with DummyExchangeGateway."""
    
    def test_execute_buy_order(self):
        """execute should work for BUY action."""
        gw = DummyExchangeGateway()
        cfg = RealExecutorConfig(symbol="BTCUSDT")
        ex = RealExecutor(cfg, gw)
        
        decision = {
            "action": "BUY",
            "quantity": 1.0,
        }
        report = ex.execute(decision)
        
        assert report["success"] is True
        assert report["filled_qty"] == 1.0
        assert "exchange_order_id" in report["meta"]
    
    def test_execute_sell_not_supported(self):
        """execute should fail for SELL action (not yet supported)."""
        gw = DummyExchangeGateway()
        cfg = RealExecutorConfig(symbol="BTCUSDT")
        ex = RealExecutor(cfg, gw)
        
        decision = {
            "action": "SELL",
            "quantity": 1.0,
        }
        report = ex.execute(decision)
        
        assert report["success"] is False
        assert "only BUY" in report["error"]
    
    def test_execute_zero_quantity_fails(self):
        """execute should fail for zero quantity."""
        gw = DummyExchangeGateway()
        cfg = RealExecutorConfig(symbol="BTCUSDT")
        ex = RealExecutor(cfg, gw)
        
        decision = {
            "action": "BUY",
            "quantity": 0.0,
        }
        report = ex.execute(decision)
        
        assert report["success"] is False
        assert "quantity must be > 0" in report["error"]
