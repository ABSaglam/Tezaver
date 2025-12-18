# Tezaver Bulut - Protective Order Tests
"""
Tests for protective order logic (IDs, Config, API compat).
"""

import pytest
from unittest.mock import MagicMock
from tezaver.bulut.services.idempotency import IdempotencyService
from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
from tezaver.bulut.core.config import BulutConfig

def test_client_order_id_length():
    # Binance limit 36
    # Prefixes tbsl_ (5 chars), tbtp_ (5 chars)
    
    key = "2025-12-18T12:00:00:BTCUSDT:OPEN_LONG"
    
    # SL
    cid_sl = IdempotencyService.make_client_order_id(key, prefix="tbsl_", max_len=36)
    assert cid_sl.startswith("tbsl_")
    assert len(cid_sl) <= 36
    
    # TP
    cid_tp = IdempotencyService.make_client_order_id(key, prefix="tbtp_", max_len=36)
    assert cid_tp.startswith("tbtp_")
    assert len(cid_tp) <= 36
    
    # Stability
    assert cid_sl == IdempotencyService.make_client_order_id(key, prefix="tbsl_", max_len=36)

import asyncio

def test_protective_order_payload_structure():
    # We can't easily mock async client request method without more setup (aioresponses)
    # But we can check if method exists and params look ok via mock
    
    config = BulutConfig()
    client = BinanceFuturesSigned(config)
    client._request = MagicMock()
    # Mock await
    async def mock_resp(*args, **kwargs):
        return {"orderId": 123}
    client._request.side_effect = mock_resp
    
    async def run_test():
        await client.place_stop_market_close_all(
            symbol="BTCUSDT",
            stop_price=95000.0,
            client_order_id="tbsl_123"
        )
    
    asyncio.run(run_test())
    
    # Verify call args
    client._request.assert_called()
    args = client._request.call_args
    # args[0] is tuple (method, url, params) usually if positional? 
    # _request(method, endpoint, params)
    
    params = args[0][2] # 3rd arg
    
    assert params["symbol"] == "BTCUSDT"
    assert params["type"] == "STOP_MARKET"
    assert params["closePosition"] == "true"
    assert "quantity" not in params
    assert params["priceProtect"] == "TRUE"
