# Tezaver Bulut - Quantity Calculator
"""
Calculates order quantity with precision rules.
"""

from typing import Optional
from decimal import Decimal, ROUND_DOWN

# We will need exchange info filters later.
# For now simple logic.

class QuantityCalculator:
    
    @staticmethod
    def calculate_qty(
        symbol: str, 
        price: float, 
        notional: float,
        step_size: float = 0.001, # Fallback
        min_qty: float = 0.001    # Fallback
    ) -> float:
        """
        Calculate quantity based on notional and price.
        Applies step_size rounding (DOWN) and min_qty check.
        """
        if price <= 0:
            return 0.0
            
        raw_qty = notional / price
        
        if raw_qty < min_qty:
            return 0.0
            
        # Round down to step_size
        # qty - (qty % step_size) generally works
        # or use decimal
        
        # Decimal approach for precision
        d_qty = Decimal(str(raw_qty))
        d_step = Decimal(str(step_size))
        
        # Quantize equivalent involves dividing, floor, multiplying
        # (qty // step) * step
        
        # Simple math with float tolerance
        steps = int(raw_qty / step_size)
        final_qty = steps * step_size
        
        # Round to avoid 0.00100000001 issues
        # guess precision from step size string length?
        # 0.001 -> 3 decimals
        decimals = 0
        s_step = str(float(step_size))
        if "." in s_step:
            decimals = len(s_step.split(".")[1])
            
        return round(final_qty, decimals)
