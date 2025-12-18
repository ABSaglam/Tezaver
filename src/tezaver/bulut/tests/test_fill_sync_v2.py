import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone

from tezaver.bulut.services.fill_sync import FillSyncService, FillSummary
from tezaver.bulut.core.config import BulutConfig

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.get_user_trades = AsyncMock()
    return client

@pytest.fixture
def mock_telemetry():
    return MagicMock()

@pytest.fixture
def mock_persistence():
    p = MagicMock()
    p.insert_order_fills = MagicMock()
    p.upsert_trade_audit_from_fills = MagicMock()
    return p

@pytest.fixture
def mock_time_sync():
    ts = MagicMock()
    ts.now_ms = MagicMock(return_value=1700000000000)
    return ts

@pytest.mark.asyncio
async def test_fill_sync_filters_by_order_id(mock_client, mock_telemetry, mock_persistence, mock_time_sync):
    config = BulutConfig()
    service = FillSyncService(config, mock_client, mock_telemetry, mock_persistence, mock_time_sync)
    
    # Mock trades return
    mock_client.get_user_trades.return_value = [
        {"symbol": "BTCUSDT", "orderId": 123, "id": "t1", "price": "40000", "qty": "0.1", "realizedPnl": "10", "commission": "1", "time": 1700000000000},
        {"symbol": "BTCUSDT", "orderId": 123, "id": "t2", "price": "41000", "qty": "0.1", "realizedPnl": "15", "commission": "1", "time": 1700000000100},
        {"symbol": "BTCUSDT", "orderId": 999, "id": "t3", "price": "42000", "qty": "0.1", "realizedPnl": "0", "commission": "1", "time": 1700000000200},
    ]
    
    summary = await service.sync_order_fills("BTCUSDT", order_id=123)
    
    assert summary is not None
    assert summary.qty == 0.2
    assert summary.vwap == 40500.0
    assert summary.realized_pnl == 25.0
    assert summary.commission == 2.0
    assert summary.net_pnl == 23.0
    assert summary.ts_first == 1700000000000
    assert summary.ts_last == 1700000000100
    
    # Verify persistence call
    assert mock_persistence.insert_order_fills.called
    # Only 2 matches should be passed to persistence? 
    # Current implementation passes the matches filtered by orderId.
    passed_fills = mock_persistence.insert_order_fills.call_args[0][0]
    assert len(passed_fills) == 2

@pytest.mark.asyncio
async def test_fill_sync_empty_trades(mock_client, mock_telemetry, mock_persistence, mock_time_sync):
    config = BulutConfig()
    service = FillSyncService(config, mock_client, mock_telemetry, mock_persistence, mock_time_sync)
    
    mock_client.get_user_trades.return_value = []
    
    summary = await service.sync_order_fills("BTCUSDT", order_id=123)
    assert summary is None
    assert mock_telemetry.emit.called # FILL_SYNC_EMPTY

@pytest.mark.asyncio
async def test_fill_sync_fail_api(mock_client, mock_telemetry, mock_persistence, mock_time_sync):
    config = BulutConfig()
    service = FillSyncService(config, mock_client, mock_telemetry, mock_persistence, mock_time_sync)
    
    mock_client.get_user_trades.return_value = {"error": True, "msg": "API Error"}
    
    summary = await service.sync_order_fills("BTCUSDT", order_id=123)
    assert summary is None
    # Ensure fail telemetry
    # Logic in service: if trades.get("error"): emit FILL_SYNC_FAIL
    any_fail = any(call[0][0] == "FILL_SYNC_FAIL" for call in mock_telemetry.emit.call_args_list)
    assert any_fail
