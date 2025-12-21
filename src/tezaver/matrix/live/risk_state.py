from enum import Enum
from typing import List, Dict, Set, Any
import logging

class RiskMode(Enum):
    NORMAL = "NORMAL"
    SAFE_MODE = "SAFE_MODE"
    HALTED = "HALTED"

class RiskStateManager:
    """
    MX-5160: Emergency Kill Switch + Safe Mode State Machine.
    Unifies triggers from all security guardrails.
    """
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.mode = RiskMode.NORMAL
        self.reasons: Set[str] = set()

    def enter_safe_mode(self, reason: str):
        """Transitions to SAFE_MODE (new orders blocked)."""
        if self.mode == RiskMode.HALTED:
            return # HALTED is irreversible/higher priority
        
        self.mode = RiskMode.SAFE_MODE
        self.reasons.add(reason)
        logging.warning(f"Engine entered SAFE_MODE. Reason: {reason}")

    def enter_halted(self, reason: str):
        """Transitions to HALTED (all orders blocked)."""
        self.mode = RiskMode.HALTED
        self.reasons.add(reason)
        logging.critical(f"Engine HALTED! Reason: {reason}")

    def recover(self, reason_to_remove: str) -> bool:
        """Attempts to remove a reason and return to NORMAL if clear."""
        if reason_to_remove in self.reasons:
            self.reasons.remove(reason_to_remove)
        
        if not self.reasons and self.mode != RiskMode.HALTED:
            self.mode = RiskMode.NORMAL
            return True
        return False

    def can_place_order(self, intent: str) -> (bool, str):
        """
        Policy enforcement for order placement.
        - Tr: Emir gönderilip gönderilemeyeceğine karar verir.
        """
        if self.mode == RiskMode.HALTED:
            return False, "HALTED"
        
        if self.mode == RiskMode.SAFE_MODE:
            if intent == "OPEN":
                return False, "SAFE_MODE:OPEN_BLOCKED"
            # CLOSE/REDUCE_ONLY is allowed in SAFE_MODE by default (MX-5160 policy)
            return True, ""

        return True, ""

    def get_status(self) -> Dict[str, Any]:
        """Summary for UI/Telemetry."""
        return {
            "mode": self.mode.value,
            "is_safe": self.mode != RiskMode.NORMAL,
            "reasons": list(self.reasons)
        }
