# Matrix V2 Live DataFeed
"""
Live market data feed implementation.
"""

from ..core.datafeed import IDataFeed


class LiveDataFeed(IDataFeed):
    """
    Live data feed from exchange.
    
    Provides real-time OHLCV data from connected exchange.
    """
    
    def __init__(self) -> None:
        """Initialize live data feed."""
        pass
    
    def get_next_bar(self, symbol: str, timeframe: str) -> dict | None:
        """
        Get the next bar of real-time OHLCV data.
        
        Args:
            symbol: Trading symbol (e.g., "BTCUSDT").
            timeframe: Bar timeframe (e.g., "15m", "1h").
            
        Returns:
            Dictionary with OHLCV data, or None if unavailable.
            
        Raises:
            NotImplementedError: Implementation pending.
        """
        raise NotImplementedError("Live data feed not yet implemented")
