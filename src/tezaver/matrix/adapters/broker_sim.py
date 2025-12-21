from tezaver.matrix.ports.broker_port import BrokerPort
from tezaver.matrix.core.order_lifecycle import Order, OrderStatus

class SimBroker(BrokerPort):
    """
    MXI-1120: Generic Sim Broker with Fee and Slippage support.
    """
    def __init__(self, fee_pct: float = 0.001, slippage_pct: float = 0.0005, fault: str = None):
        """
        Args:
            fee_pct: Trading fee percentage (0.001 = 0.1%)
            slippage_pct: Slippage percentage (0.0005 = 0.05%)
            fault: "TIMEOUT", "REJECT", "PARTIAL" or None
        """
        self.fee_pct = fee_pct
        self.slippage_pct = slippage_pct
        self.fault = fault

    def place_order(self, order: Order) -> Order:
        # Simulate logic: Immediate ACK -> FILL (or fault)
        
        # 1. ACK
        order.status = OrderStatus.ACKED
        
        # 2. Fill Logic
        if self.fault == "TIMEOUT":
            order.status = OrderStatus.TIMEOUT
        elif self.fault == "REJECT":
            order.status = OrderStatus.REJECTED
        elif self.fault == "PARTIAL":
            order.status = OrderStatus.PARTIALLY_FILLED
        else:
            # Happy path with Fee & Slippage (MXI-1120)
            # Buy: Fill higher, Sell: Fill lower
            direction = 1 if order.qty > 0 else -1
            fill_price = order.limit_price * (1 + (direction * self.slippage_pct))
            
            order.fill_price = fill_price
            order.fill_qty = order.qty
            order.fee_cost = abs(order.qty * fill_price * self.fee_pct)
            order.status = OrderStatus.FILLED
            
        return order

    def cancel_order(self, order_id: str) -> None:
        # Sim cancel: always success if tracked... 
        # But this sim is stateless regarding open orders.
        pass
