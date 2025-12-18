# Tezaver Bulut - Price Rounding
"""
Price rounding utilities for exchange compliance.
"""

from typing import Optional

def round_price_to_tick(symbol: str, price: float) -> float:
    """
    Round price to tick size.
    v0.09: Hardcoded fallback to 2 decimals if filter missing.
    v0.10: Will fetch filters from exchangeInfo.
    """
    # Deterministic fallback for now
    # TODO: Load from data/exchange/binance_futures_filters.json
    
    return round(price, 2)
