# Matrix Real Executor
"""
Real executor that bridges IExecutor to IExchangeGateway.

This module provides the skeleton for executing real orders via exchange gateway.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any

from tezaver.matrix.live.live_gateway import (
    IExchangeGateway,
    ExchangeOrderRequest,
    OrderSide,
)


@dataclass
class RealExecutorConfig:
    """Configuration for RealExecutor."""
    symbol: str
    # Future: hedge mode, isolated/cross margin, etc.


class RealExecutor:
    """
    IExecutor implementation for real exchange orders.
    
    Note:
    - Currently only supports "market BUY" scenario.
    - Close/TP/SL can be extended later.
    """

    def __init__(self, cfg: RealExecutorConfig, gateway: IExchangeGateway):
        self._cfg = cfg
        self._gateway = gateway

    def execute(self, decision: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a trade decision via exchange gateway.
        
        Args:
            decision: Dict with 'action', 'quantity', etc.
            
        Returns:
            ExecutionReport-like dict with success, filled_qty, avg_price, error.
        """
        action = decision.get("action", "")
        
        # Only BUY action supported for now
        if action != "BUY":
            return {
                "success": False,
                "filled_qty": 0.0,
                "avg_price": None,
                "error": f"RealExecutor currently supports only BUY, got {action}",
            }

        qty = float(decision.get("quantity", 0.0))
        if qty <= 0.0:
            return {
                "success": False,
                "filled_qty": 0.0,
                "avg_price": None,
                "error": "quantity must be > 0 for RealExecutor",
            }

        req = ExchangeOrderRequest(
            symbol=self._cfg.symbol,
            side=OrderSide.BUY,
            quantity=qty,
            price=None,  # Market order by default
        )
        res = self._gateway.place_order(req)

        return {
            "success": res.success,
            "filled_qty": res.filled_qty,
            "avg_price": res.avg_price,
            "error": res.error,
            "meta": {
                "exchange_order_id": res.order_id,
                "exchange_raw": res.raw,
            },
        }
