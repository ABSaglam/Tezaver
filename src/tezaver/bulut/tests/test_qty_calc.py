# Tezaver Bulut - Qty Calc Tests
"""
Tests for quantity calculator logic.
"""

import pytest
from unittest.mock import MagicMock, patch
from tezaver.bulut.services.qty_calc import QuantityCalculator


def test_qty_calc_basic():
    """Test basic calculation with mocked context."""
    with patch("tezaver.bulut.services.qty_calc.get_context") as mock_get_ctx:
        ctx = MagicMock()
        ctx.exchangeinfo_cache.get_filters.return_value = {
            "stepSize": 1.0, "minQty": 0.0
        }
        ctx.config.block_if_filters_missing = True
        mock_get_ctx.return_value = ctx
        
        # Price 100, Notional 500 => Qty 5
        qty = QuantityCalculator.calculate_qty("BTCUSDT", 100.0, 500.0)
        assert qty == 5.0


def test_qty_calc_rounding_down():
    """Test rounding down to step size."""
    with patch("tezaver.bulut.services.qty_calc.get_context") as mock_get_ctx:
        ctx = MagicMock()
        ctx.config.block_if_filters_missing = True
        mock_get_ctx.return_value = ctx
        
        # Step = 0.001
        ctx.exchangeinfo_cache.get_filters.return_value = {
            "stepSize": 0.001, "minQty": 0.0
        }
        # Price 100, Notional 500.55 => Raw 5.0055 => 5.005
        qty = QuantityCalculator.calculate_qty("BTCUSDT", 100.0, 500.55)
        assert qty == 5.005
        
        # Step 0.1
        ctx.exchangeinfo_cache.get_filters.return_value = {
            "stepSize": 0.1, "minQty": 0.0
        }
        qty2 = QuantityCalculator.calculate_qty("BTCUSDT", 100.0, 500.55)
        assert qty2 == 5.0


def test_qty_calc_min_qty():
    """Test min qty filter."""
    with patch("tezaver.bulut.services.qty_calc.get_context") as mock_get_ctx:
        ctx = MagicMock()
        ctx.config.block_if_filters_missing = True
        ctx.telemetry = MagicMock()
        mock_get_ctx.return_value = ctx
        
        # Min Qty 0.001, result below => 0.0
        ctx.exchangeinfo_cache.get_filters.return_value = {
            "stepSize": 0.001, "minQty": 0.001
        }
        # Price 100000, Notional 10 => 0.0001 < 0.001
        qty = QuantityCalculator.calculate_qty("BTCUSDT", 100000.0, 10.0)
        assert qty == 0.0
