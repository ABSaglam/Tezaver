from tezaver.matrix.core.order_lifecycle import (
    OrderLifecycleTracker, Order, OrderStatus, simulate_fault
)
import pytest

@pytest.mark.core
def test_lifecycle_happy_path():
    tracker = OrderLifecycleTracker(run_id="test_run_1")  # New API requires run_id
    o = Order("1", "BTC", "BUY", 1.0)
    
    tracker.submit(o)
    assert o.status == OrderStatus.SUBMITTED
    
    tracker.ack(o)
    assert o.status == OrderStatus.ACKED
    
    tracker.fill(o, fill_price=1.0)  # Updated: new signature is fill(order, fill_price=None)
    assert o.status == OrderStatus.FILLED

def test_fault_injection_timeout():
    o = Order("2", "BTC", "BUY", 1.0)
    simulate_fault(o, "TIMEOUT")
    assert o.status == OrderStatus.TIMEOUT

def test_invalid_transition():
    tracker = OrderLifecycleTracker(run_id="test_run_3")  # New API requires run_id
    o = Order("3", "BTC", "BUY", 1.0)
    # Cannot ack NEW order (tracker logic check missing in sample code but good practice)
    # The sample implementation 'submit' checks state.
    
    o.status = OrderStatus.FILLED
    with pytest.raises(ValueError):
        tracker.submit(o)
