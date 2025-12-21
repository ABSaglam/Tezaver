from tezaver.matrix.core.order_lifecycle import (
    OrderLifecycleTracker, Order, OrderStatus, simulate_fault
)
import pytest

@pytest.mark.core
def test_lifecycle_happy_path():
    tracker = OrderLifecycleTracker()
    o = Order("1", "BTC", "BUY", 1.0)
    
    tracker.submit(o)
    assert o.status == OrderStatus.SUBMITTED
    
    tracker.ack(o)
    assert o.status == OrderStatus.ACKED
    
    tracker.fill(o, 1.0, True)
    assert o.status == OrderStatus.FILLED

def test_fault_injection_timeout():
    o = Order("2", "BTC", "BUY", 1.0)
    simulate_fault(o, "TIMEOUT")
    assert o.status == OrderStatus.TIMEOUT

def test_invalid_transition():
    tracker = OrderLifecycleTracker()
    o = Order("3", "BTC", "BUY", 1.0)
    # Cannot ack NEW order (tracker logic check missing in sample code but good practice)
    # The sample implementation 'submit' checks state.
    
    o.status = OrderStatus.FILLED
    with pytest.raises(ValueError):
        tracker.submit(o)
