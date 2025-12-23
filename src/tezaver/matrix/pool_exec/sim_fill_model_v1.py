"""
SIM Fill Model V1
==================

Fee + Slippage simulation for SIM execution.
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
from datetime import datetime, timezone

# Defaults
DEFAULT_FEE_BPS = 4.0        # 0.04%
DEFAULT_SLIPPAGE_BPS = 8.0   # 0.08%

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def apply_bps(price: float, bps: float, action: str) -> float:
    """
    Apply basis points slippage (worse direction for user).
    
    Args:
        price: Reference price
        bps: Basis points (1 bps = 0.01%)
        action: "OPEN_POSITION" or "CLOSE_POSITION"
        
    Returns:
        Effective price after slippage
    """
    factor = bps / 10000.0
    
    if action == "OPEN_POSITION":
        # User buys higher (worse for user)
        return price * (1 + factor)
    elif action == "CLOSE_POSITION":
        # User sells lower (worse for user)
        return price * (1 - factor)
    else:
        # Default: worse direction
        return price * (1 + factor)

def compute_fee(notional: float, fee_bps: float) -> float:
    """Compute fee cost from notional and fee_bps."""
    return notional * (fee_bps / 10000.0)

def compute_slippage_cost(ref_price: float, eff_price: float, notional: float) -> float:
    """Compute slippage cost as notional impact."""
    if ref_price == 0:
        return 0.0
    price_diff_ratio = abs(eff_price - ref_price) / ref_price
    return notional * price_diff_ratio

@dataclass
class SimFillResultV1:
    """Simulated fill result with fee + slippage."""
    order_key: str
    intent_id: str
    action: str
    symbol: str
    timeframe: Optional[str]
    ref_price: float
    eff_price: float
    notional: float
    qty: float
    fee_bps: float
    slippage_bps: float
    fee_cost: float
    slippage_cost: float
    ts_iso: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_key": self.order_key,
            "intent_id": self.intent_id,
            "action": self.action,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "ref_price": self.ref_price,
            "eff_price": self.eff_price,
            "notional": self.notional,
            "qty": self.qty,
            "fee_bps": self.fee_bps,
            "slippage_bps": self.slippage_bps,
            "fee_cost": self.fee_cost,
            "slippage_cost": self.slippage_cost,
            "ts_iso": self.ts_iso
        }

def simulate_fill(
    order_key: str,
    intent_id: str,
    action: str,
    symbol: str,
    timeframe: Optional[str],
    ref_price: float,
    notional: float,
    fee_bps: float = DEFAULT_FEE_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS
) -> SimFillResultV1:
    """
    Simulate a fill with fee + slippage.
    
    Args:
        order_key: Order key
        intent_id: Intent ID
        action: OPEN_POSITION or CLOSE_POSITION
        symbol: Trading symbol
        timeframe: Timeframe
        ref_price: Reference price
        notional: Trade notional
        fee_bps: Fee in basis points
        slippage_bps: Slippage in basis points
        
    Returns:
        SimFillResultV1
    """
    eff_price = apply_bps(ref_price, slippage_bps, action)
    qty = notional / eff_price if eff_price > 0 else 0.0
    fee_cost = compute_fee(notional, fee_bps)
    slippage_cost = compute_slippage_cost(ref_price, eff_price, notional)
    
    return SimFillResultV1(
        order_key=order_key,
        intent_id=intent_id,
        action=action,
        symbol=symbol,
        timeframe=timeframe,
        ref_price=ref_price,
        eff_price=eff_price,
        notional=notional,
        qty=qty,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        fee_cost=fee_cost,
        slippage_cost=slippage_cost,
        ts_iso=now_iso()
    )
