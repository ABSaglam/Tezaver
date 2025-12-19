import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
import json
import os

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.income_sync import IncomeSyncService
from tezaver.bulut.services.portfolio_risk import PortfolioRiskService
from tezaver.bulut.services.group_caps_loader import GroupCapsLoader
from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned

@pytest.fixture
def mock_telemetry():
    return MagicMock()

@pytest.fixture
def clean_db():
    db_path = "test_income.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    persistence = SqlitePersistence(db_path)
    yield persistence
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.mark.asyncio
async def test_upsert_income_events(clean_db):
    events = [
        {
            "tranId": "1000",
            "symbol": "BTCUSDT",
            "incomeType": "FUNDING_FEE",
            "income": "-0.5",
            "asset": "USDT",
            "time": 1600000000000,
            "info": "test"
        },
        {
            "tranId": "1001",
            "symbol": "ETHUSDT",
            "incomeType": "FUNDING_FEE",
            "income": "-0.2",
            "asset": "USDT",
            "time": 1600000000000, # Same time
            "info": "test2"
        },
        {
             # Duplicate tranId
            "tranId": "1000", 
            "symbol": "BTCUSDT",
            "incomeType": "FUNDING_FEE",
            "income": "-0.5",
            "asset": "USDT",
            "time": 1600000000000,
            "info": "test"
        }
    ]
    
    count = clean_db.upsert_income_events(events)
    # tranID 1000 inserted once, 1001 inserted once. Total 2.
    # Note: upsert_income_events returns rowcount of insert.
    # If INSERT OR IGNORE is used, rowcount might reflect ignored also in some sqlite versions?
    # No, rowcount usually returns inserted rows for standard sqlite3 python driver with insert or ignore.
    # Let's verify by checking DB.
    
    conn = clean_db._get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM income_events")
    rows = cursor.fetchone()[0]
    conn.close()
    
    assert rows == 2
    
    # Check aggregation function
    date_str = datetime.fromtimestamp(1600000000000/1000.0, timezone.utc).strftime("%Y-%m-%d")
    stats = clean_db.get_today_income_sum_utc(types=["FUNDING_FEE"], date_str=date_str)
    
    assert stats["FUNDING_FEE"] == pytest.approx(-0.7)
    assert stats["TOTAL"] == pytest.approx(-0.7)
    assert stats["non_usdt_count"] == 0

@pytest.mark.asyncio
async def test_non_usdt_aggregation(clean_db):
    events = [
        {
            "tranId": "2000",
            "symbol": "BTCUSDT",
            "incomeType": "COMMISSION", 
            "income": "-0.001",
            "asset": "BNB",  # Non-USDT
            "time": 1600000000000
        }
    ]
    clean_db.upsert_income_events(events)
    
    date_str = datetime.fromtimestamp(1600000000000/1000.0, timezone.utc).strftime("%Y-%m-%d")
    stats = clean_db.get_today_income_sum_utc(types=["COMMISSION"], date_str=date_str)
    
    # BNB value is -0.001 but asset is BNB.
    # TOTAL (USDT only) should be 0.0
    assert stats["TOTAL"] == 0.0
    # v0.22+: Aggregation is strictly USDT-based. Unconverted income = 0.0 USDT.
    assert stats["COMMISSION"] == 0.0 
    assert stats["non_usdt_count"] == 1

@pytest.mark.asyncio
async def test_income_sync_service_flow(clean_db, mock_telemetry):
    config = BulutConfig(
        income_sync_enabled=True,
        income_sync_types="FUNDING_FEE,INSURANCE_CLEAR",
        income_sync_lookback_hours=1
    )
    
    client = MagicMock(spec=BinanceFuturesSigned)
    client.get_income_history = AsyncMock(return_value=[
        {
            "tranId": "3000",
            "symbol": "BTCUSDT",
            "incomeType": "FUNDING_FEE",
            "income": "-1.0",
            "asset": "USDT",
            "time": 1700000000000
        }
    ])
    
    time_sync = MagicMock()
    time_sync.now_ms.return_value = 1700000005000 # 5s after event
    
    service = IncomeSyncService(config, client, clean_db, mock_telemetry, time_sync)
    
    # Test sync_now
    res = await service.sync_now()
    
    assert res["inserted"] == 1
    assert clean_db.get_income_last_sync_ms() == 1700000000001 # Advanced cursor
    
    # Verify client called for both types (if split string works)
    # config types: "FUNDING_FEE,INSURANCE_CLEAR"
    assert client.get_income_history.call_count == 2
    
@pytest.mark.asyncio
async def test_portfolio_risk_integration(clean_db, mock_telemetry):
    config = BulutConfig(
        daily_loss_limit_usdt=10.0,
        include_income_in_daily_loss_guard=True,
        income_sync_types="FUNDING_FEE"
    )
    
    # Pre-populate DB with huge funding cost that exceeds limit
    events = [{
        "tranId": "4000",
        "symbol": "BTCUSDT",
        "incomeType": "FUNDING_FEE",
        "income": "-15.0", # Exceeds 10.0 limit
        "asset": "USDT",
        "time": int(datetime.now(timezone.utc).timestamp() * 1000)
    }]
    clean_db.upsert_income_events(events)
    
    # Also some trade pnl
    # We need trade_audit records for get_today_net_pnl_utc
    # Let's mock get_today_net_pnl_utc manually or insert audit?
    # Inserting audit is cleaner.
    # Inserting audit is cleaner.
    # But mark_position_closed requires the position to exist first (rowcount check).
    clean_db.upsert_position_open(
        symbol="ETHUSDT",
        entry_ts=datetime.now(timezone.utc),
        entry_price=100.0, qty=1.0, notional=100.0,
        sl_pct=0.01, tp_pct=0.02,
        last_update_ts_ms=1
    )
    clean_db.mark_position_closed(
        symbol="ETHUSDT",
        close_ts=datetime.now(timezone.utc),
        exit_price=100, entry_price=100, qty=1,
        pnl_usdt=2.0, # +2 profit
        last_update_ts_ms=10 # > 1
    )
    # Total PnL = +2 (Trade) - 15 (Income) = -13. Limit is -10. Should BLOCK.
    
    group_caps = MagicMock(spec=GroupCapsLoader)
    group_caps.get_group.return_value = "A"
    group_caps.get_cap.return_value = 10
    group_caps.get_open_counts.return_value = {}

    risk = PortfolioRiskService(config, clean_db, group_caps, mock_telemetry)
    
    allowed, code, details = risk.check_entry_allowed("BTCUSDT", 100, 0)
    
    assert allowed is False
    assert code == "DAILY_LOSS_GUARD"
    assert details["today_total_pnl"] == pytest.approx(-13.0)
    
