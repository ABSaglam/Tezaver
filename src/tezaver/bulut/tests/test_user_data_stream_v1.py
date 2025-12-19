# Tezaver Bulut - User Data Stream Tests (v0.22)
"""
Tests for UserDataStream service using v0.22 reducer pattern.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.user_data_stream import UserDataStream
from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

@pytest.fixture
def mock_deps():
    config = BulutConfig(user_data_ws_enabled=True)
    client = MagicMock(spec=BinanceFuturesSigned)
    client.create_listen_key = AsyncMock(return_value="test_listen_key")
    client.keepalive_listen_key = AsyncMock()
    client.close_listen_key = AsyncMock()
    
    telemetry = MagicMock(spec=NdjsonTelemetry)
    
    # Mock Context & State Reducer (v0.22)
    ctx = MagicMock()
    ctx.state_reducer = MagicMock()
    ctx.state_reducer.apply_order_update = MagicMock()
    ctx.state_reducer.apply_account_update = MagicMock()
    
    return config, client, telemetry, ctx

@pytest.mark.asyncio
async def test_start_creates_listen_key(mock_deps):
    """Test that start() calls run_forever which creates listen key."""
    config, client, telemetry, ctx = mock_deps
    stream = UserDataStream(config, client, telemetry)
    
    # Mock run_forever to be a simple coroutine that runs once
    # Since start() spawns run_forever as a task, we need to test run_forever directly
    # with mocked loops to verify create_listen_key is called
    with patch.object(stream, '_ws_loop', AsyncMock()), \
         patch.object(stream, '_keepalive_loop', AsyncMock()):
        # Run run_forever directly (since it's what actually calls create_listen_key)
        await stream.run_forever(ctx)
    
    client.create_listen_key.assert_called_once()
    assert stream._listen_key == "test_listen_key"
    assert stream._ctx == ctx

@pytest.mark.asyncio
async def test_process_order_update(mock_deps):
    """Test ORDER_TRADE_UPDATE handling via reducer."""
    config, client, telemetry, ctx = mock_deps
    stream = UserDataStream(config, client, telemetry)
    stream._ctx = ctx
    
    # Set reducer (v0.22)
    reducer = MagicMock()
    reducer.apply_order_update = MagicMock()
    stream.set_reducer(reducer)
    
    # ORDER_TRADE_UPDATE payload
    payload = {
        "e": "ORDER_TRADE_UPDATE",
        "E": 1600000000000,
        "o": {
            "s": "BTCUSDT",
            "i": 12345,
            "c": "client_1",
            "X": "FILLED",
            "x": "TRADE",
            "z": "0.1",
            "ap": "50000.0",
            "T": 1600000000000
        }
    }
    
    await stream._handle_message(payload)
    
    # Verify reducer.apply_order_update was called with the order data
    reducer.apply_order_update.assert_called_once()
    call_args = reducer.apply_order_update.call_args
    assert call_args[0][0] == payload["o"]  # First arg is order data
    assert call_args[1]["source"] == "USER_DATA"  # source kwarg

@pytest.mark.asyncio
async def test_process_account_update(mock_deps):
    """Test ACCOUNT_UPDATE handling via reducer."""
    config, client, telemetry, ctx = mock_deps
    stream = UserDataStream(config, client, telemetry)
    stream._ctx = ctx
    
    # Set reducer (v0.22)
    reducer = MagicMock()
    reducer.apply_account_update = MagicMock()
    stream.set_reducer(reducer)
    
    # ACCOUNT_UPDATE payload (Position closed)
    payload = {
        "e": "ACCOUNT_UPDATE",
        "E": 1600000000000,
        "a": {
            "P": [
                {"s": "BTCUSDT", "pa": "0", "ep": "0.0"},  # Closed
                {"s": "ETHUSDT", "pa": "1.0", "ep": "3000.0"}  # Open
            ]
        }
    }
    
    await stream._handle_message(payload)
    
    # Verify reducer.apply_account_update was called with account data
    reducer.apply_account_update.assert_called_once()
    call_args = reducer.apply_account_update.call_args
    # Account data should include _E (event time) injected by handler
    account_data = call_args[0][0]
    assert account_data.get("_E") == 1600000000000
    assert call_args[1]["source"] == "USER_DATA"

@pytest.mark.asyncio
async def test_stop_closes_stream(mock_deps):
    """Test stop() properly cleans up."""
    config, client, telemetry, ctx = mock_deps
    stream = UserDataStream(config, client, telemetry)
    stream._listen_key = "key"
    stream._running = True
    
    await stream.stop()
    
    assert stream._running is False
    assert stream._listen_key is None
    client.close_listen_key.assert_called_once()
