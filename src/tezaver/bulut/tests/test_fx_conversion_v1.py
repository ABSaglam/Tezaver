import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone
import json
import time

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.fx_rate_cache import FxRateCache
from tezaver.bulut.services.fx_recompute import FxRecomputeService
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.binance_futures_signed import BinanceFuturesSigned
from tezaver.bulut.services.fill_sync import FillSyncService, FillSummary
from tezaver.bulut.services.income_sync import IncomeSyncService

@pytest.fixture
def clean_persistence(tmp_path):
    db_path = tmp_path / "test_fx.db"
    if db_path.exists():
        db_path.unlink()
    # Init DB schema
    p = SqlitePersistence(str(db_path))
    # Create tables if not exist (constructor does it usually)
    return p

@pytest.fixture
def mock_client():
    client = MagicMock(spec=BinanceFuturesSigned)
    client.get_book_ticker = AsyncMock()
    client.get_last_price = AsyncMock()
    client.get_income_history = AsyncMock()
    client.get_user_trades = AsyncMock()
    return client

@pytest.fixture
def config():
    return BulutConfig(
        fx_fallback_last_price=True,
        fx_price_mode="BOOK_MID",
        fx_ttl_seconds=1,
        alert_on_non_usdt_fee=True
    )

@pytest.mark.asyncio
async def test_fx_rate_cache_logic(clean_persistence, mock_client, config):
    # Setup cache
    cache = FxRateCache(config, mock_client, clean_persistence, MagicMock())
    
    # Mock bookticker return
    # {symbol: BNBUSDT, bidPrice: 599.0, askPrice: 601.0} -> mid 600.0
    mock_client.get_book_ticker.return_value = {
        "symbol": "BNBUSDT",
        "bidPrice": "599.0", 
        "askPrice": "601.0"
    }
    
    # 1. Fetch fresh
    rate = await cache.get_rate("BNB")
    assert rate == 600.0
    assert mock_client.get_book_ticker.call_count == 1
    
    # 2. Verify persistence
    saved = clean_persistence.get_fx_rate("BNB")
    assert saved is not None
    assert saved["rate"] == 600.0
    
    # 3. Hit cache (TTL 1s)
    rate2 = await cache.get_rate("BNB")
    assert rate2 == 600.0
    assert mock_client.get_book_ticker.call_count == 1 # Should not call again
    
    # 4. Expire cache
    time.sleep(1.1)
    mock_client.get_book_ticker.return_value = {
        "symbol": "BNBUSDT", "bidPrice": "609.0", "askPrice": "611.0"
    } # mid 610
    
    rate3 = await cache.get_rate("BNB")
    assert rate3 == 610.0
    assert mock_client.get_book_ticker.call_count == 2
    
@pytest.mark.asyncio
async def test_fill_sync_conversion(clean_persistence, mock_client, config):
    # Prepare cache with known rates
    cache = FxRateCache(config, mock_client, clean_persistence, MagicMock())
    # Pre-seed BNB rate in DB to avoid async call inside sync (if we implemented sync correctly)
    clean_persistence.upsert_fx_rate("BNB", "USDT", 600.0, "TEST")
    
    svc = FillSyncService(config, mock_client, MagicMock(), clean_persistence, MagicMock(), fx_cache=cache)
    
    # Mock trades: 1 BNB as fee
    mock_client.get_user_trades.return_value = [{
        "symbol": "BTCUSDT",
        "orderId": 100,
        "qty": "1.0",
        "price": "50000.0",
        "realizedPnl": "100.0",
        "commission": "0.1",
        "commissionAsset": "BNB",
        "time": int(time.time()*1000)
    }]
    
    summary = await svc.sync_order_fills("BTCUSDT", order_id=100)
    
    assert summary is not None
    assert summary.commission_asset == "BNB"
    assert summary.commission == 0.1
    
    # Expect conversion: 0.1 BNB * 600 = 60 USDT
    assert summary.fee_usdt == 60.0
    assert summary.fx_rate == 600.0
    
    # Verify Audit persistence (upsert_order_fills is called, but executor calls upsert_audit)
    # FillSyncService inserts fills to `order_fills`. It does NOT update `trade_audit`. 
    # Executor updates trade_audit using summary.
    # In this test we just check summary.

@pytest.mark.asyncio
async def test_recompute_logic(clean_persistence, mock_client, config):
    # Setup cache
    cache = FxRateCache(config, mock_client, clean_persistence, MagicMock())
    recomputer = FxRecomputeService(config, cache, clean_persistence, MagicMock())
    
    now_ms = int(time.time()*1000)
    ts_str = datetime.now(timezone.utc).isoformat()
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Insert Unconverted Income
    conn = clean_persistence._get_conn()
    conn.execute("""
        INSERT INTO income_events (tran_id, symbol, income_type, asset, income, time_ms, time_ts, raw_json)
        VALUES ('T1', 'BNBUSDT', 'COMMISSION', 'BNB', 1.0, ?, ?, '{}')
    """, (now_ms, ts_str))
    
    # 2. Insert Unconverted Audit
    conn.execute("""
        INSERT INTO trade_audit (symbol, close_ts, exit_reason, entry_price, exit_price, qty, pnl_usdt, gross_pnl_usdt, fee_asset, fee_native, cycle_ts)
        VALUES ('BTCUSDT', ?, 'TP', 50000, 51000, 1.0, 1000, 1000, 'BNB', 0.1, ?)
    """, (ts_str, ts_str))
    conn.commit()
    conn.close()
    
    # Mock Rate for BNB
    mock_client.get_book_ticker.return_value = {"symbol": "BNBUSDT", "bidPrice": "599.0", "askPrice": "601.0"}
    
    # Run recompute
    stats = await recomputer.recompute_today_utc()
    
    assert stats["income_fixed"] == 1
    assert stats["audit_fixed"] == 1
    
    # Verify Income Update
    conn = clean_persistence._get_conn()
    row = conn.execute("SELECT income_usdt, fx_rate FROM income_events WHERE tran_id='T1'").fetchone()
    assert row[0] == 600.0 # 1.0 * 600
    conn.close()
    
    # Verify Audit Update
    conn = clean_persistence._get_conn()
    row2 = conn.execute("SELECT fee_usdt, net_pnl_usdt FROM trade_audit WHERE symbol='BTCUSDT'").fetchone()
    # 0.1 * 600 = 60.0 fee
    # Net = Gross (1000) - Fee (60) = 940
    assert row2[0] == 60.0
    assert row2[1] == 940.0
    conn.close()

