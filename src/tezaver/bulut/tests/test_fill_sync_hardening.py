import pytest
import asyncio
import time
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
import dataclasses

from tezaver.bulut.engine.executor import Executor
from tezaver.bulut.services.fill_sync import FillSyncService, FillSummary
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.schemas.trade_plan_v1 import TradePlanV1, TradeDecision, TradeSide, StopConfig, StopType

@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    # Create config via init since frozen
    ctx.config = BulutConfig(
        fill_sync_max_wait_seconds=1, # faster tests
        fill_sync_retry_interval_ms=10,
        alert_on_non_usdt_fee=True
    )
    ctx.persistence = MagicMock()
    ctx.telemetry = MagicMock()
    ctx.fill_sync = MagicMock() # Will be overwritten or detailed in tests
    ctx.bars_store = MagicMock()
    return ctx

@pytest.mark.asyncio
async def test_fill_sync_retry_eventually_finds_fills(mock_ctx):
    executor = Executor(mock_ctx.config)
    
    # Mock fill_sync behavior
    mock_summary = FillSummary(
        symbol="BTCUSDT", order_id=123, qty=1.0, vwap=50000.0,
        realized_pnl=100.0, commission=1.0, commission_asset="USDT",
        net_pnl=99.0, ts_first=1000, ts_last=2000
    )
    
    mock_ctx.fill_sync.sync_order_fills = AsyncMock(side_effect=[None, None, mock_summary])
    
    plan = TradePlanV1(
        symbol="BTCUSDT", 
        decision=TradeDecision.CLOSE,
        side=TradeSide.LONG,
        notional_usdt=1000.0,
        sl=StopConfig(type=StopType.PCT, value=1.0),
        tp=StopConfig(type=StopType.PCT, value=2.0),
        plan_ts=datetime.now(timezone.utc),
        reasons={"exit_reason": "MANUAL"}, idempotency_key="test_key"
    )
    
    mock_ctx.persistence.get_position.return_value = {"qty": 1.0, "entry_price": 40000.0}
    
    executor._client = MagicMock()
    executor._client.create_order = AsyncMock(return_value={"orderId": 123, "avgPrice": "50010"})
    executor._client.get_order_by_client_id = AsyncMock()
    
    mock_ctx.bars_store.get_last_closed.return_value = MagicMock(c=50010)
    mock_ctx.persistence.try_mark_executing.return_value = True
    
    await executor._execute_single_plan(plan, mock_ctx)
    
    # Check call count
    assert mock_ctx.fill_sync.sync_order_fills.call_count == 3
    # Check upgrade attempt
    assert mock_ctx.persistence.upgrade_trade_audit_from_fills.called

@pytest.mark.asyncio
async def test_upgrade_estimated_to_user_trades(mock_ctx):
    from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
    import os
    
    db_path = "test_audit_upgrade.db"
    if os.path.exists(db_path): os.remove(db_path)
    
    p = SqlitePersistence(db_path=db_path)
    
    # 1. Insert an ESTIMATED audit record with order_id
    ts = datetime.now(timezone.utc)
    p.mark_position_closed(
        symbol="BTCUSDT", close_ts=ts, exit_price=50000.0,
        entry_price=40000.0, qty=0.1, pnl_usdt=1000.0,
        pnl_is_estimated=True, exit_reason="MANUAL",
        cycle_ts=ts,
        close_order_id=555
    )
    
    # 2. Upgrade it
    summary = {
        "realized_pnl": 1050.0,
        "commission": 2.0,
        "commission_asset": "USDT",
        "vwap": 50500.0,
        "qty": 0.1,
        "ts_last": int(time.time() * 1000)
    }
    
    ok = p.upgrade_trade_audit_from_fills("BTCUSDT", close_order_id=555, summary=summary)
    assert ok is True
    
    audit_up = p.get_latest_audit(1)[0]
    assert audit_up["pnl_source"] == "USER_TRADES"
    assert audit_up["audit_upgraded"] == 1
    assert audit_up["net_pnl_usdt"] == 1048.0
    
    os.remove(db_path)

@pytest.mark.asyncio
async def test_non_usdt_fee_alert(mock_ctx):
    executor = Executor(mock_ctx.config)
    
    mock_summary = FillSummary(
        symbol="BTCUSDT", order_id=123, qty=1.0, vwap=50000.0,
        realized_pnl=100.0, commission=0.01, commission_asset="BNB",
        net_pnl=100.0,
        ts_first=1000, ts_last=2000
    )
    
    mock_ctx.fill_sync.sync_order_fills = AsyncMock(return_value=mock_summary)
    
    plan = TradePlanV1(
        symbol="BTCUSDT", 
        decision=TradeDecision.CLOSE,
        side=TradeSide.LONG,
        notional_usdt=1000.0,
        sl=StopConfig(type=StopType.PCT, value=1.0),
        tp=StopConfig(type=StopType.PCT, value=2.0),
        plan_ts=datetime.now(timezone.utc),
        reasons={"exit_reason": "MANUAL"}, idempotency_key="test_key_alert"
    )
    
    executor._client = MagicMock()
    executor._client.create_order = AsyncMock(return_value={"orderId": 123, "avgPrice": "50000"})
    mock_ctx.persistence.get_position.return_value = {"qty": 1.0, "entry_price": 40000.0}
    mock_ctx.persistence.try_mark_executing.return_value = True
    mock_ctx.bars_store.get_last_closed.return_value = MagicMock(c=50000)

    await executor._execute_single_plan(plan, mock_ctx)
    
    assert mock_ctx.persistence.insert_alert.called
    call_args = mock_ctx.persistence.insert_alert.call_args[1]
    assert call_args["code"] == "NON_USDT_FEE_UNACCOUNTED"



