# Tezaver Bulut - Quantity Calculator
"""
Calculates order quantity with precision rules.
"""

from typing import Optional
from decimal import Decimal, ROUND_FLOOR
from tezaver.bulut.core.context import get_context

class QuantityCalculator:
    """
    Calculates trade quantities respecting exchange filters.
    """
    
    @staticmethod
    def calculate_qty(symbol: str, price: float, notional_usdt: float) -> float:
        """
        Calculate quantity from notional, rounding down to stepSize.
        Checks minQty.
        Returns 0.0 if blocked or invalid.
        """
        if price <= 0:
            return 0.0
            
        ctx = get_context()
        filters = ctx.exchangeinfo_cache.get_filters(symbol)
        
        step_size = 0.0
        min_qty = 0.0
        
        if filters:
            step_size = filters.get("stepSize", 0.0)
            min_qty = filters.get("minQty", 0.0)
            
        if step_size <= 0:
            if ctx.config.block_if_filters_missing:
                ctx.telemetry.emit_filters_missing(symbol, "qty_calc")
                return 0.0
            else:
                # Fallback: assume 3 decimals
                raw_qty = notional_usdt / price
                return round(raw_qty, 3)
                
        # Calculate raw qty
        raw_qty = notional_usdt / price
        
        # Round DOWN to stepSize (using Decimal to avoid float errors)
        d_qty = Decimal(str(raw_qty))
        d_step = Decimal(str(step_size))
        
        # qty / step -> floor -> * step
        rounded_qty = (d_qty / d_step).to_integral_value(rounding=ROUND_FLOOR) * d_step
        final_qty = float(rounded_qty)
        
        # MinQty Check
        if final_qty < min_qty:
            ctx.telemetry.emit_filters_violation(symbol, f"QTY_BELOW_MIN: {final_qty} < {min_qty}")
            return 0.0
            
        return final_qty
