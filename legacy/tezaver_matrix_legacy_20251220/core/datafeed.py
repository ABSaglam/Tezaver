# Matrix V2 DataFeed Module
"""
Data feed protocol for Matrix v2.
"""

from typing import Protocol


class IDataFeed(Protocol):
    """
    Protocol for market data feeds.
    
    Implementations provide OHLCV bar data from various sources:
    - Live: Real-time exchange data
    - Replay: Historical data for backtesting/wargame
    """
    
    def get_next_bar(self, symbol: str, timeframe: str) -> dict | None:
        """
        Get the next bar of OHLCV data.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT").
            timeframe: Bar timeframe (e.g., "15m", "1h").
            
        Returns:
            Dictionary with OHLCV data, or None if no more data.
            Expected keys: open, high, low, close, volume, timestamp
        """
        ...
