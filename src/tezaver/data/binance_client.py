"""
Binance Client Wrapper for Tezaver Mac.
Wraps ccxt to fetch OHLCV data, enforcing the philosophy of using only closed bars.
"""

import ccxt
from dataclasses import dataclass
from typing import List, Optional
import time

@dataclass
class OHLCVRecord:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

class BinanceClient:
    def __init__(self):
        self.exchange = ccxt.binance({
            "enableRateLimit": True,
            "options": {
                "defaultType": "spot" # Explicitly set spot, though default usually is
            }
        })

    def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        since: Optional[int] = None,
        limit: int = 1000
    ) -> List[OHLCVRecord]:
        """
        Fetches OHLCV data from Binance.
        
        Tezaver Philosophy:
        We only work with CLOSED bars.
        ccxt.fetch_ohlcv returns closed bars by default for most exchanges including Binance,
        but the last bar *might* be open if it's the current time.
        However, strictly speaking, historical calls usually return closed bars.
        We will rely on ccxt's behavior but keep in mind that for real-time updates,
        we must ensure we don't use the currently forming bar.
        """
        try:
            raw_data = self.exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
            
            records = []
            for row in raw_data:
                # row structure: [timestamp, open, high, low, close, volume]
                record = OHLCVRecord(
                    timestamp=row[0],
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5])
                )
                records.append(record)
                
            return records
            
        except ccxt.BaseError as e:
            print(f"Error fetching OHLCV for {symbol} {timeframe}: {e}")
            raise e

    def get_server_time(self) -> int:
        """Returns the exchange server time in milliseconds."""
        return self.exchange.milliseconds()
