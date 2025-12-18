# Tezaver Bulut - REST Kline Conversion Tests
"""
Tests for transforming REST Kline data to BarV1.
"""

from datetime import datetime, timezone
import pytest
from tezaver.bulut.services.binance_futures_rest import BinanceFuturesRest
from tezaver.bulut.core.config import BulutConfig

# Mock responses
# [open_time, open, high, low, close, volume, close_time, ...]
# Times in ms

def test_parse_kline():
    """Verify kline array parsing."""
    config = BulutConfig()
    service = BinanceFuturesRest(config)
    
    # Mock kline data
    # 2025-01-01 10:00:00 UTC = 1735725600000
    # 15m later = 1735726500000
    ts_open = 1735725600000
    ts_close = 1735726499999
    
    kline = [
        ts_open,
        "100.0", "105.0", "95.0", "102.5", "500.0",
        ts_close,
        "ignore", "ignore"
    ]
    
    bar = service._parse_kline("BTCUSDT", "15m", kline)
    
    assert bar.symbol == "BTCUSDT"
    assert bar.o == 100.0
    assert bar.h == 105.0
    assert bar.l == 95.0
    assert bar.c == 102.5
    assert bar.v == 500.0
    assert bar.open_ts.timestamp() == 1735725600.0
    
    # Check close ts logic (approx)
    assert int(bar.close_ts.timestamp() * 1000) == ts_close
