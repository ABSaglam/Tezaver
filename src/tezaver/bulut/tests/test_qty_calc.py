# Tezaver Bulut - Qty Calc Tests
"""
Tests for quantity calculator logic.
"""

import pytest
from tezaver.bulut.services.qty_calc import QuantityCalculator

def test_qty_calc_basic():
    """Test basic calculation."""
    # Price 100, Notional 500 => Qty 5
    qty = QuantityCalculator.calculate_qty("BTCUSDT", 100.0, 500.0)
    assert qty == 5.0

def test_qty_calc_rounding_down():
    """Test rounding down to step size."""
    # Price 100, Notional 500.55
    # Raw Qty = 5.0055
    # Step = 0.001
    # Expect 5.005
    qty = QuantityCalculator.calculate_qty("BTCUSDT", 100.0, 500.55, step_size=0.001)
    assert qty == 5.005
    
    # Step 0.1
    # Expect 5.0
    qty2 = QuantityCalculator.calculate_qty("BTCUSDT", 100.0, 500.55, step_size=0.1)
    assert qty2 == 5.0

def test_qty_calc_min_qty():
    """Test min qty filter."""
    # Price 100000, Notional 10 => 0.0001
    # Min Qty 0.001 => Should be 0.0
    qty = QuantityCalculator.calculate_qty("BTCUSDT", 100000.0, 10.0, min_qty=0.001)
    assert qty == 0.0
