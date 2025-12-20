from tezaver.matrix.ports.broker_port import BrokerPort
from tezaver.matrix.core.order_lifecycle import Order, OrderStatus

class SimBroker(BrokerPort):
    def __init__(self, fault: str = None):
        """
        Args:
            fault: "TIMEOUT", "REJECT", "PARTIAL" or None
        """
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
            # Happy path
            order.status = OrderStatus.FILLED
            
        return order

    def cancel_order(self, order_id: str) -> None:
        # Sim cancel: always success if tracked... 
        # But this sim is stateless regarding open orders.
        pass
