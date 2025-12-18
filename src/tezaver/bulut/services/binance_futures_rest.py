# Tezaver Bulut - Binance Futures REST Service
"""
Async REST client for Binance Futures.
Fetches Klines (OHLCV).
"""

import aiohttp
import time
from typing import List, Optional, Any
from datetime import datetime, timezone

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.schemas.bar_v1 import BarV1


class BinanceFuturesRest:
    """
    Binance Futures REST Client.
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
        self._base_url = (
            config.rest_base_url_testnet 
            if config.use_testnet 
            else config.rest_base_url
        )
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def create_session(self):
        """Create aiohttp session if needed."""
        if not self._session:
            self._session = aiohttp.ClientSession()
            
    async def close(self):
        """Close session."""
        if self._session:
            await self._session.close()
            self._session = None
            
    async def get_latest_closed_bar(self, symbol: str, interval: str = "15m") -> Optional[BarV1]:
        """
        Get the latest CLOSED bar for a symbol.
        Checks last 2 bars, returns the most recent one that is fully closed.
        """
        # Ensure session
        if not self._session:
            await self.create_session()
            
        limit = self._config.kline_limit
        url = f"{self._base_url}/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        try:
            async with self._session.get(url, params=params, timeout=5) as resp:
                if resp.status != 200:
                    print(f"[BINANCE_REST] Error {resp.status} for {symbol}")
                    return None
                    
                data = await resp.json()
                if not data or not isinstance(data, list):
                    return None
                
                # Evaluate bars to find latest closed
                # Binance Kline: [open_time, open, high, low, close, volume, close_time, ...]
                # All times in ms.
                
                current_time_ms = int(time.time() * 1000)
                
                # Check from newest (last) to oldest
                for kline in reversed(data):
                    close_time_ms = kline[6]
                    
                    # Rule: Bar is closed if current_time >= close_time + 1ms
                    if current_time_ms > close_time_ms:
                        return self._parse_kline(symbol, interval, kline)
                
                return None
                
        except Exception as e:
            print(f"[BINANCE_REST] Exception for {symbol}: {e}")
            return None

    def _parse_kline(self, symbol: str, interval: str, kline: list) -> BarV1:
        """Parse raw kline array to BarV1."""
        # [0:open_time, 1:o, 2:h, 3:l, 4:c, 5:v, 6:close_time, ...]
        open_ts = datetime.fromtimestamp(kline[0] / 1000.0, tz=timezone.utc)
        close_ts = datetime.fromtimestamp(kline[6] / 1000.0, tz=timezone.utc) # This is usually open + interval - 1ms
        
        # Adjust close_ts to readable boundary? 
        # Usually close_ts in binance is e.g. 10:14:59.999.
        # BarV1 schema expects close_ts. Let's keep it exact or round up?
        # Let's keep exact for precision.
        
        return BarV1(
            symbol=symbol,
            tf=interval,
            open_ts=open_ts,
            close_ts=close_ts,
            o=float(kline[1]),
            h=float(kline[2]),
            l=float(kline[3]),
            c=float(kline[4]),
            v=float(kline[5]),
            is_closed=True
        )
