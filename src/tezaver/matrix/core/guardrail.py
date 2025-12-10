# Matrix V2 Guardrail Module
"""
Risk management and guardrail controls for Matrix v2.
"""

from dataclasses import dataclass, field

from .types import TradeDecision
from .account import AccountState


@dataclass
class GuardrailConfig:
    """
    Configuration for guardrail risk controls.
    """
    max_open_positions: int = 3
    max_daily_loss_pct: float = 5.0  # Maximum daily loss as percentage of capital
    min_affinity_score: float | None = None  # Optional affinity threshold


@dataclass
class GuardrailDecision:
    """
    Result of a guardrail check.
    """
    allow: bool
    reason_code: str  # e.g., "OK", "MAX_POSITIONS", "DAILY_LOSS_LIMIT"
    details: dict[str, object] = field(default_factory=dict)


class GuardrailController:
    """
    Controller for risk management rules.
    
    Validates trading decisions against configured risk limits.
    """
    
    def __init__(self, config: GuardrailConfig) -> None:
        """
        Initialize GuardrailController with config.
        
        Args:
            config: GuardrailConfig with risk limits.
        """
        self.config = config
    
    def check_new_trade(
        self,
        profile_id: str,
        account: AccountState,
        decision: TradeDecision,
    ) -> GuardrailDecision:
        """
        Check if a new trade decision is allowed by guardrail rules.
        
        Args:
            profile_id: The trading profile ID.
            account: Current account state.
            decision: The trade decision to validate.
            
        Returns:
            GuardrailDecision indicating if trade is allowed.
        """
        # Placeholder implementation - always allow for now
        # Real logic will check:
        # 1. Number of open positions vs max_open_positions
        # 2. Daily PnL vs max_daily_loss_pct
        # 3. Affinity score vs min_affinity_score (if applicable)
        
        return GuardrailDecision(
            allow=True,
            reason_code="OK",
            details={"profile_id": profile_id, "decision_id": decision.decision_id},
        )
