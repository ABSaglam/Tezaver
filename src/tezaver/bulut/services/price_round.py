from decimal import Decimal, ROUND_FLOOR, ROUND_CEILING, ROUND_HALF_UP
from typing import Optional
from tezaver.bulut.core.context import get_context

class FiltersMissingError(Exception):
    pass

def round_to_tick(symbol: str, price: float, direction: str = "NEAREST") -> float:
    """
    Round price to tick size using ExchangeInfo Cache.
    direction: "UP" (Ceiling), "DOWN" (Floor), "NEAREST" (Standard)
    """
    ctx = get_context()
    filters = ctx.exchangeinfo_cache.get_filters(symbol)
    
    tick_size = 0.0
    if filters:
        tick_size = filters.get("tickSize", 0.0)
    
    if tick_size <= 0:
        if ctx.config.block_if_filters_missing:
            ctx.telemetry.emit_filters_missing(symbol, "price_round")
            raise FiltersMissingError(f"Tick size missing for {symbol}")
        else:
            # Fallback
            ctx.telemetry.emit("WARN_TICKSIZE_FALLBACK", {"symbol": symbol, "price": price})
            return round(price, 2)
            
    # Perform rounding
    d_price = Decimal(str(price))
    d_tick = Decimal(str(tick_size))
    
    if direction == "UP":
        # Ceiling to tick
        # price / tick -> ceil -> * tick
        rounded = (d_price / d_tick).to_integral_value(rounding=ROUND_CEILING) * d_tick
    elif direction == "DOWN":
        # Floor to tick
        rounded = (d_price / d_tick).to_integral_value(rounding=ROUND_FLOOR) * d_tick
    else:
        # Nearest
        rounded = (d_price / d_tick).to_integral_value(rounding=ROUND_HALF_UP) * d_tick
        
    return float(rounded)

# Backwards compatibility alias if needed, or update callers
def round_price_to_tick(symbol: str, price: float) -> float:
    return round_to_tick(symbol, price, "NEAREST")
