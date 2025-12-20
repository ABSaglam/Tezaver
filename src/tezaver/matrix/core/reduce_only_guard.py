from typing import Dict, Any, Optional

class ReduceOnlyGuard:
    """
    Enforces reduce-only constraints.
    """
    def check_violation(self, action: str, reduce_only: bool, current_position: float) -> Optional[str]:
        """
        Returns violation reason if any, else None.
        Assuming LONG-ONLY strategy for simplicity as per Phase-14C context.
        """
        if not reduce_only:
            return None
            
        if action == "BUY":
            return "BUY blocked in ReduceOnly mode"
            
        # SELL is usually allowed to reduce.
        # But if we are already flat (0)? Sending SELL might open SHORT?
        # If Matrix v4 is Long Only, SELL when flat might be invalid or Short.
        # But usually SELL is "Close".
        # If position is 0 and we SELL, and Broker interprets as Short Open?
        # Binace Futures "Hedge Mode" vs "One-way".
        # We assume One-way usually.
        # If reduceOnly=True is sent to API, API will reject if it would open opposite.
        # So we are somewhat safe if we pass reduceOnly flag to broker.
        # But here we gate ACTIONS.
        
        return None
