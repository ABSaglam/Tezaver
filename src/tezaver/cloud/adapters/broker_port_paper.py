"""
CLOUD-1020: CloudBrokerPortPaper - Paper broker for cloud service.
Same interface as Matrix SimBroker.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class PaperOrder:
    """Order representation for paper trading."""
    order_id: str
    symbol: str
    side: str  # BUY/SELL
    qty: float
    price: float
    status: str = "NEW"
    fill_price: Optional[float] = None
    fill_qty: Optional[float] = None
    fee: float = 0.0
    slippage: float = 0.0
    created_at: str = ""
    filled_at: str = ""


class CloudBrokerPaper:
    """
    CLOUD-1020: Paper broker for cloud service.
    Simulates order execution with configurable fee/slippage.
    """
    
    def __init__(self, fee_pct: float = 0.001, slippage_pct: float = 0.0005):
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self.orders: List[PaperOrder] = []
        self.order_counter = 0
    
    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: float
    ) -> PaperOrder:
        """
        Place a paper order - immediately filled with slippage.
        """
        self.order_counter += 1
        order_id = f"paper_{self.order_counter}"
        
        # Apply slippage
        direction = 1 if side == "BUY" else -1
        fill_price = price * (1 + direction * self.slippage_pct)
        
        # Calculate fee
        notional = abs(qty * fill_price)
        fee = notional * self.fee_pct
        
        order = PaperOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            status="FILLED",
            fill_price=fill_price,
            fill_qty=qty,
            fee=fee,
            slippage=abs(fill_price - price),
            created_at=datetime.now().isoformat(),
            filled_at=datetime.now().isoformat()
        )
        
        self.orders.append(order)
        return order
    
    def get_orders(self) -> List[PaperOrder]:
        """Get all orders."""
        return self.orders
    
    def get_order(self, order_id: str) -> Optional[PaperOrder]:
        """Get order by ID."""
        for o in self.orders:
            if o.order_id == order_id:
                return o
        return None
    
    def to_trade_audit(self) -> List[Dict]:
        """Convert orders to trade audit format."""
        return [
            {
                "order_id": o.order_id,
                "symbol": o.symbol,
                "side": o.side,
                "qty": o.qty,
                "price": o.price,
                "fill_price": o.fill_price,
                "fee": o.fee,
                "slippage": o.slippage,
                "filled_at": o.filled_at
            }
            for o in self.orders
        ]
