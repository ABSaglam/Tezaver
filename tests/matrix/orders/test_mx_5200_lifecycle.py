import pytest
import time
from tezaver.matrix.core.order_lifecycle import Order, OrderStatus, OrderLifecycleTracker
from tezaver.matrix.adapters.broker_sim import SimBroker

def test_order_lifecycle_happy_path():
    order = Order(order_id="ord_1", symbol="BTCUSDT", side="LONG", qty=1.0, limit_price=50000.0)
    tracker = OrderLifecycleTracker(run_id="test_run")
    
    tracker.submit(order)
    assert order.status == OrderStatus.SUBMITTED
    
    tracker.ack(order, exchange_id="ex_1")
    assert order.status == OrderStatus.ACKED
    assert order.exchange_order_id == "ex_1"
    
    tracker.fill(order, fill_price=50050.0)
    assert order.status == OrderStatus.FILLED
    assert order.fill_qty == 1.0
    assert order.fill_price == 50050.0
    assert len(order.history) == 3

def test_order_lifecycle_timeout_and_cancel():
    order = Order(order_id="ord_2", symbol="BTCUSDT", side="LONG", qty=1.0, limit_price=50000.0)
    tracker = OrderLifecycleTracker(run_id="test_run")
    
    tracker.submit(order)
    tracker.ack(order)
    
    tracker.timeout(order)
    assert order.status == OrderStatus.TIMEOUT
    
    # Try to cancel after timeout (terminal)
    tracker.canceled(order, reason="TIMEOUT_EXPIRED")
    assert order.status == OrderStatus.TIMEOUT # State should remain terminal

def test_order_partial_fill():
    order = Order(order_id="ord_3", symbol="BTCUSDT", side="LONG", qty=1.0, limit_price=50000.0)
    tracker = OrderLifecycleTracker(run_id="test_run")
    
    tracker.submit(order)
    tracker.ack(order)
    
    tracker.partial_fill(order, fill_qty_delta=0.4, fill_price=50100.0)
    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.fill_qty == 0.4
    assert order.fill_price == 50100.0
    
    tracker.partial_fill(order, fill_qty_delta=0.3, fill_price=50200.0)
    # Expected weighted avg: (0.4*50100 + 0.3*50200) / 0.7 = (20040 + 15060) / 0.7 = 35100 / 0.7 = 50142.857
    assert order.fill_qty == 0.7
    assert round(order.fill_price, 2) == 50142.86
    
    tracker.fill(order, fill_price=50000.0)
    assert order.status == OrderStatus.FILLED
    assert order.fill_qty == 1.0
    # Final weighted avg: (35100 + 0.3*50000) / 1.0 = (35100 + 15000) = 50100.0
    assert order.fill_price == 50100.0

def test_order_reject():
    order = Order(order_id="ord_4", symbol="BTCUSDT", side="LONG", qty=1.0, limit_price=50000.0)
    tracker = OrderLifecycleTracker(run_id="test_run")
    
    tracker.submit(order)
    tracker.reject(order, reason="INSUFFICIENT_FUNDS")
    assert order.status == OrderStatus.REJECTED
    assert order.history[-1]["reason"] == "INSUFFICIENT_FUNDS"
