# Matrix V2 Guardrail Module
"""
Risk management and guardrail controls for Matrix v2.

Supports profile-aware decisions with CoinPage V2 integration.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Dict, TYPE_CHECKING

from .types import TradeDecision
from .account import AccountState

if TYPE_CHECKING:
    from .profile import MatrixCellProfile


# =============================================================================
# Guardrail V2 Types
# =============================================================================

class GuardrailEnvironment(str, Enum):
    """Execution environment for guardrail decisions."""
    WARGAME = "wargame"
    LIVE = "live"


@dataclass
class GuardrailContext:
    """Context for profile-aware guardrail decisions."""
    symbol: str
    timeframe: str
    profile_id: str
    environment: GuardrailEnvironment = GuardrailEnvironment.WARGAME
    risk_per_trade_requested: Optional[float] = None


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
    
    Extended with profile status and risk contract info for v2.
    """
    allow: bool
    reason_code: str  # e.g., "OK", "MAX_POSITIONS", "DAILY_LOSS_LIMIT", "PROFILE_DISABLED"
    details: Dict[str, Any] = field(default_factory=dict)
    
    # V2 fields: profile awareness
    profile_status: Optional[str] = None  # APPROVED / EXPERIMENTAL / DISABLED / UNKNOWN
    risk_contract_max: Optional[float] = None  # max_risk_per_trade from contract


class GuardrailController:
    """
    Controller for risk management rules.
    
    Validates trading decisions against configured risk limits.
    Supports profile-aware decisions with LIVE/WARGAME environment logic.
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
    
    def check_profile_and_risk(
        self,
        profile: Optional["MatrixCellProfile"],
        ctx: GuardrailContext,
    ) -> GuardrailDecision:
        """
        Profile + environment + requested risk decision maker.
        
        Rules:
        - LIVE mode: blocks DISABLED and EXPERIMENTAL profiles
        - WARGAME mode: allows everything, only carries info
        
        Args:
            profile: MatrixCellProfile from CoinPage V2 (or None if not found).
            ctx: GuardrailContext with symbol, timeframe, environment, etc.
            
        Returns:
            GuardrailDecision with allow/block and profile metadata.
        """
        # Profile not found: fail-open with warning
        if profile is None:
            return GuardrailDecision(
                allow=True,
                reason_code="PROFILE_NOT_FOUND",
                details={
                    "profile_id": ctx.profile_id,
                    "environment": ctx.environment.value,
                },
                profile_status="UNKNOWN",
                risk_contract_max=None,
            )
        
        status = (profile.status or "UNKNOWN").upper()
        
        # Extract risk_contract_max from profile.risk_contract (StrategyRiskContractV1)
        risk_contract_max: Optional[float] = None
        rc = getattr(profile, "risk_contract", None)
        if rc is not None:
            risk_contract_max = getattr(rc, "max_risk_per_trade", None)
        
        # LIVE environment rules
        if ctx.environment == GuardrailEnvironment.LIVE:
            if status == "DISABLED":
                return GuardrailDecision(
                    allow=False,
                    reason_code="PROFILE_DISABLED",
                    details={
                        "symbol": ctx.symbol,
                        "timeframe": ctx.timeframe,
                        "profile_id": ctx.profile_id,
                        "environment": ctx.environment.value,
                        "risk_per_trade_requested": ctx.risk_per_trade_requested,
                    },
                    profile_status=status,
                    risk_contract_max=risk_contract_max,
                )
            
            if status == "EXPERIMENTAL":
                return GuardrailDecision(
                    allow=False,
                    reason_code="PROFILE_EXPERIMENTAL_WARGAME_ONLY",
                    details={
                        "symbol": ctx.symbol,
                        "timeframe": ctx.timeframe,
                        "profile_id": ctx.profile_id,
                        "environment": ctx.environment.value,
                        "risk_per_trade_requested": ctx.risk_per_trade_requested,
                    },
                    profile_status=status,
                    risk_contract_max=risk_contract_max,
                )
        
        # WARGAME: allow everything, carry info
        return GuardrailDecision(
            allow=True,
            reason_code="OK",
            details={
                "symbol": ctx.symbol,
                "timeframe": ctx.timeframe,
                "profile_id": ctx.profile_id,
                "environment": ctx.environment.value,
                "risk_per_trade_requested": ctx.risk_per_trade_requested,
            },
            profile_status=status,
            risk_contract_max=risk_contract_max,
        )

