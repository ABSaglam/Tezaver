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
    
    # Mock Context & Persistence
    ctx = MagicMock()
    ctx.persistence.upsert_trade_audit_event = MagicMock()
    ctx.persistence.mark_position_closed = MagicMock()
    
    return config, client, telemetry, ctx

@pytest.mark.asyncio
async def test_start_creates_listen_key(mock_deps):
    config, client, telemetry, ctx = mock_deps
    stream = UserDataStream(config, client, telemetry)
    
    # Don't actually run WS loop in test start check (it spawns task)
    # We can mock _ws_loop to do nothing
    with patch.object(stream, '_ws_loop', AsyncMock()), \
         patch.object(stream, '_keepalive_loop', AsyncMock()):
        await stream.start(ctx)
        
    client.create_listen_key.assert_called_once()
    assert stream._listen_key == "test_listen_key"
    assert stream._running is True

@pytest.mark.asyncio
async def test_process_order_update(mock_deps):
    config, client, telemetry, ctx = mock_deps
    stream = UserDataStream(config, client, telemetry)
    stream._ctx = ctx
    
    # ORDER_TRADE_UPDATE payload example
    payload = {
        "e": "ORDER_TRADE_UPDATE",
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
    
    ctx.persistence.upsert_trade_audit_event.assert_called_once_with(
        order_id="12345",
        client_id="client_1",
        symbol="BTCUSDT",
        status="FILLED",
        exec_type="TRADE",
        filled_qty=0.1,
        avg_price=50000.0,
        event_time=1600000000000
    )

@pytest.mark.asyncio
async def test_process_account_update(mock_deps):
    config, client, telemetry, ctx = mock_deps
    stream = UserDataStream(config, client, telemetry)
    stream._ctx = ctx
    
    # ACCOUNT_UPDATE payload example (Position closed)
    payload = {
        "e": "ACCOUNT_UPDATE",
        "a": {
            "P": [
                {"s": "BTCUSDT", "pa": "0", "ep": "0.0"}, # Closed
                {"s": "ETHUSDT", "pa": "1.0", "ep": "3000.0"} # Open
            ]
        }
    }
    
    await stream._handle_message(payload)
    
    # Should mark BTCUSDT closed
    ctx.persistence.mark_position_closed.assert_called_with(
        symbol="BTCUSDT",
        close_reason="EVENT_CLOSED",
        close_order_id=None
    )
    # Should NOT mark ETHUSDT closed
    call_args_list = ctx.persistence.mark_position_closed.call_args_list
    assert len(call_args_list) == 1
    assert call_args_list[0].kwargs["symbol"] == "BTCUSDT"

@pytest.mark.asyncio
async def test_stop_closes_stream(mock_deps):
    config, client, telemetry, ctx = mock_deps
    stream = UserDataStream(config, client, telemetry)
    stream._listen_key = "key"
    stream._running = True
    
    await stream.stop()
    
    assert stream._running is False
    assert stream._listen_key is None
    client.close_listen_key.assert_called_once()
