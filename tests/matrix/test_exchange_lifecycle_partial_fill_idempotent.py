import json
import pytest
import os
from tezaver.matrix.core.exchange_lifecycle import ExchangeOrderLifecycleTracker

def test_exchange_lifecycle_partial_fill_idempotent(tmp_path):
    home = str(tmp_path)
    sid = "S1"
    os.makedirs(tmp_path / "cloud_runtime" / "strategies" / sid, exist_ok=True)
    
    tracker = ExchangeOrderLifecycleTracker(home, sid)
    
    # 1. New Partial Fill (0.5)
    # cumQty (z) = 0.5
    evt1 = {"c": "C1", "i": 100, "X": "PARTIALLY_FILLED", "z": "0.5"}
    d1 = tracker.update_order(evt1)
    assert d1 == 0.5
    
    # 2. Duplicate Event (Same z)
    d2 = tracker.update_order(evt1)
    assert d2 == 0.0 # Idempotent
    
    # 3. Next Fill (Total 1.0)
    evt2 = {"c": "C1", "i": 100, "X": "FILLED", "z": "1.0"}
    d3 = tracker.update_order(evt2)
    assert d3 == 0.5 # 1.0 - 0.5
    
    # Verify State
    orders = tracker.orders
    assert orders["C1"]["status"] == "FILLED"
    assert orders["C1"]["cumQty"] == 1.0
