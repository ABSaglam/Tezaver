# Live Market Data Client
"""
Market data client interface and implementations.

IMPORTANT: Market data is PUBLIC - no API key required.
Order execution requires private API keys.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Protocol, Optional
import pandas as pd


class IMarketDataClient(Protocol):
    """Interface for market data retrieval."""
    
    def get_latest_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Get latest OHLCV bars.
        
        Returns DataFrame with columns: open, high, low, close, volume, ts
        where ts is the bar open timestamp.
        """
        ...
    
    def get_server_time(self) -> datetime:
        """Get server time."""
        ...


class DummyMarketDataClient:
    """
    Dummy market data client for testing.
    
    Generates synthetic bar data.
    """
    
    def __init__(self, base_price: float = 42000.0):
        self._base_price = base_price
        self._tick_count = 0
    
    def get_latest_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Generate synthetic bars."""
        import numpy as np
        from datetime import timedelta
        
        now = datetime.utcnow()
        
        # Parse timeframe to minutes
        tf_minutes = 15
        if timeframe.endswith("m"):
            tf_minutes = int(timeframe[:-1])
        elif timeframe.endswith("h"):
            tf_minutes = int(timeframe[:-1]) * 60
        
        # Generate bar timestamps
        bar_delta = timedelta(minutes=tf_minutes)
        
        # Align to bar boundary
        bar_start = now.replace(second=0, microsecond=0)
        bar_minute = (bar_start.minute // tf_minutes) * tf_minutes
        bar_start = bar_start.replace(minute=bar_minute)
        
        bars = []
        for i in range(limit):
            ts = bar_start - bar_delta * (limit - i - 1)
            
            # Generate price with some variation
            np.random.seed(int(ts.timestamp()) % 10000)
            change = np.random.normal(0, 0.005)
            price = self._base_price * (1 + change)
            
            bars.append({
                "ts": ts,
                "open": price * 0.999,
                "high": price * 1.002,
                "low": price * 0.997,
                "close": price,
                "volume": np.random.uniform(100, 1000),
            })
        
        self._tick_count += 1
        return pd.DataFrame(bars)
    
    def get_server_time(self) -> datetime:
        """Return current UTC time."""
        return datetime.utcnow()


class BinancePublicClient:
    """
    Binance public OHLCV client (no auth required).
    
    Uses public /api/v3/klines endpoint.
    Adds is_closed flag based on server time.
    """
    
    CLOSE_GRACE_MS = 1500  # 1.5s grace period after bar close
    
    def __init__(self, base_url: str = "https://api.binance.com"):
        self._base_url = base_url
        self._session = None
        self._last_server_time_ms: int = 0
    
    def _get_session(self):
        if self._session is None:
            import requests
            self._session = requests.Session()
        return self._session
    
    def get_server_time_ms(self) -> int:
        """Get Binance server time in milliseconds."""
        url = f"{self._base_url}/api/v3/time"
        resp = self._get_session().get(url, timeout=5)
        resp.raise_for_status()
        self._last_server_time_ms = resp.json()["serverTime"]
        return self._last_server_time_ms
    
    def get_server_time(self) -> datetime:
        """Get Binance server time as datetime."""
        return datetime.utcfromtimestamp(self.get_server_time_ms() / 1000)
    
    def get_latest_bars(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV from Binance public API.
        
        Returns DataFrame with columns:
        - ts: bar open time (datetime)
        - open, high, low, close, volume
        - open_time_ms, close_time_ms: raw timestamps
        - is_closed: True if bar is finalized
        """
        import time
        
        # Map timeframe to Binance interval
        interval = timeframe  # 15m, 1h, 4h etc should work
        
        url = f"{self._base_url}/api/v3/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        }
        
        # Simple retry with backoff
        for attempt in range(3):
            try:
                resp = self._get_session().get(url, params=params, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                break
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(1 * (attempt + 1))
        
        # Get server time for is_closed calculation
        server_time_ms = self.get_server_time_ms()
        
        # Parse klines
        # Kline format: [open_time, open, high, low, close, volume, close_time, ...]
        bars = []
        for k in data:
            open_time_ms = k[0]
            close_time_ms = k[6]
            
            # Bar is closed if server_time >= close_time + grace
            is_closed = server_time_ms >= (close_time_ms + self.CLOSE_GRACE_MS)
            
            bars.append({
                "ts": datetime.utcfromtimestamp(open_time_ms / 1000),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "open_time_ms": open_time_ms,
                "close_time_ms": close_time_ms,
                "is_closed": is_closed,
            })
        
        return pd.DataFrame(bars)
