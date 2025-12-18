# Tezaver Bulut - Exchange Info Tests
"""
Tests for ExchangeInfo cache, price rounding, and quantity calculation logic.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from tezaver.bulut.services.price_round import round_to_tick, FiltersMissingError
from tezaver.bulut.services.qty_calc import QuantityCalculator
from tezaver.bulut.services.exchangeinfo_cache import ExchangeInfoCache
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import get_context

# Mock Data
MOCK_FILTERS = {
    "BTCUSDT": {
        "tickSize": 0.1,
        "stepSize": 0.001,
        "minQty": 0.001
    },
    "ETHUSDT": {
        "tickSize": 0.01,
        "stepSize": 0.01, # e.g.
        "minQty": 0.01
    }
}

@pytest.fixture
def mock_context():
    # Setup mock context with exchange cache
    ctx = MagicMock()
    # Instantiate with desired config directly (frozen dataclass)
    ctx.config = BulutConfig(block_if_filters_missing=True)
    
    mock_cache = MagicMock()
    mock_cache.get_filters.side_effect = lambda s: MOCK_FILTERS.get(s)
    ctx.exchangeinfo_cache = mock_cache
    
    # We need to inject this context globally if functions use get_context()
    # But get_context() in `core/context.py` uses a global var `_global_context`.
    # We can patch `tezaver.bulut.core.context.get_context`.
    return ctx

@patch("tezaver.bulut.services.price_round.get_context")
def test_round_to_tick(mock_get_ctx, mock_context):
    mock_get_ctx.return_value = mock_context
    mock_context.exchangeinfo_cache.get_filters.side_effect = lambda s: MOCK_FILTERS.get(s)
    
    # BTC: tick 0.1
    # Nearest
    assert round_to_tick("BTCUSDT", 95000.12, "NEAREST") == 95000.1
    assert round_to_tick("BTCUSDT", 95000.16, "NEAREST") == 95000.2
    
    # Up (SL safe?)
    # 95000.11 -> 95000.2
    assert round_to_tick("BTCUSDT", 95000.11, "UP") == 95000.2
    
    # Down (TP safe?)
    # 95000.19 -> 95000.1
    assert round_to_tick("BTCUSDT", 95000.19, "DOWN") == 95000.1
    
    # ETH: tick 0.01
    assert round_to_tick("ETHUSDT", 2000.001, "DOWN") == 2000.00
    assert round_to_tick("ETHUSDT", 2000.001, "UP") == 2000.01

@patch("tezaver.bulut.services.qty_calc.get_context")
@patch("tezaver.bulut.services.price_round.get_context")
def test_filters_missing_block(mock_get_ctx_round, mock_get_ctx_qty, mock_context):
    # Both mocks return same context
    mock_get_ctx_round.return_value = mock_context
    mock_get_ctx_qty.return_value = mock_context
    mock_context.exchangeinfo_cache.get_filters.return_value = None # No filters
    
    with pytest.raises(FiltersMissingError):
        round_to_tick("UNKNOWN", 100.0)
        
    # Qty block
    qty = QuantityCalculator.calculate_qty("UNKNOWN", 100.0, 1000.0)
    assert qty == 0.0

@patch("tezaver.bulut.services.qty_calc.get_context")
def test_qty_calc(mock_get_ctx, mock_context):
    mock_get_ctx.return_value = mock_context
    mock_context.exchangeinfo_cache.get_filters.side_effect = lambda s: MOCK_FILTERS.get(s)
    
    # BTC: step 0.001, min 0.001
    # Notional 1000, Price 100000 -> 0.01
    assert QuantityCalculator.calculate_qty("BTCUSDT", 100000.0, 1000.0) == 0.01
    
    # Step rounding DOWN
    # Raw 0.0109 -> 0.010
    assert QuantityCalculator.calculate_qty("BTCUSDT", 100000.0, 1090.0) == 0.010
    
    # Min Qty
    # Raw 0.0005 < 0.001
    # Should return 0.0
    assert QuantityCalculator.calculate_qty("BTCUSDT", 100000.0, 50.0) == 0.0
    
    # Exact step
    assert QuantityCalculator.calculate_qty("BTCUSDT", 100000.0, 100.0) == 0.001
