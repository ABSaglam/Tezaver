# Tezaver Bulut - Trade Plan Schema v1
"""
Schema definition for TradePlan v1.

Output of Decider for each trade decision.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from enum import Enum
import uuid


SCHEMA_VERSION = "trade_plan_v1"


class TradeSide(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class TradeDecision(str, Enum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"
    SKIP = "SKIP"
    HOLD = "HOLD"


class StopType(str, Enum):
    PCT = "PCT"  # Percentage-based
    ATR = "ATR"  # ATR-based
    FIXED = "FIXED"  # Fixed price


@dataclass
class StopConfig:
    """Stop loss or take profit configuration."""
    type: StopType
    value: float  # e.g., 1.0 for 1% or 2.0 for 2x ATR
    
    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "value": self.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "StopConfig":
        return cls(
            type=StopType(data.get("type", "PCT")),
            value=float(data.get("value", 0)),
        )


@dataclass
class TradePlanV1:
    """
    Trade Plan v1 Schema.
    
    Structure:
    {
        "schema": "trade_plan_v1",
        "plan_ts": "iso",
        "symbol": "BTCUSDT",
        "side": "LONG",
        "decision": "OPEN|SKIP|CLOSE",
        "notional_usdt": 100,
        "sl": {"type": "PCT", "value": 1.0},
        "tp": {"type": "PCT", "value": 2.0},
        "idempotency_key": "string",
        "reasons": {}
    }
    """
    symbol: str
    side: TradeSide
    decision: TradeDecision
    notional_usdt: float
    sl: StopConfig
    tp: StopConfig
    plan_ts: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: str = field(default_factory=lambda: str(uuid.uuid4()))
    reasons: dict = field(default_factory=dict)
    
    # Determinism Bridge v1
    policy_decision_id: str = ""
    policy_phase_at_decision: str = ""
    cycle_index: int = 0
    input_fingerprint: str = ""
    
    # Leverage (v0.22 - optional, used by sizing resolver)
    leverage: Optional[int] = None
    
    @property
    def schema(self) -> str:
        return SCHEMA_VERSION
    
    @property
    def is_actionable(self) -> bool:
        """Check if plan requires action (not SKIP)."""
        return self.decision != TradeDecision.SKIP
    
    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "plan_ts": self.plan_ts.isoformat() if isinstance(self.plan_ts, datetime) else self.plan_ts,
            "symbol": self.symbol,
            "side": self.side.value,
            "decision": self.decision.value,
            "notional_usdt": round(self.notional_usdt, 2),
            "sl": self.sl.to_dict(),
            "tp": self.tp.to_dict(),
            "idempotency_key": self.idempotency_key,
            "reasons": self.reasons,
            "policy_decision_id": self.policy_decision_id,
            "policy_phase_at_decision": self.policy_phase_at_decision,
            "cycle_index": self.cycle_index,
            "input_fingerprint": self.input_fingerprint,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Optional["TradePlanV1"]:
        """Parse from dictionary."""
        if data.get("schema") != SCHEMA_VERSION:
            return None
        
        try:
            plan_ts = data.get("plan_ts", "")
            if isinstance(plan_ts, str):
                plan_ts = datetime.fromisoformat(plan_ts.replace("Z", "+00:00"))
            
            return cls(
                symbol=data.get("symbol", ""),
                side=TradeSide(data.get("side", "LONG")),
                decision=TradeDecision(data.get("decision", "SKIP")),
                notional_usdt=float(data.get("notional_usdt", 0)),
                sl=StopConfig.from_dict(data.get("sl", {"type": "PCT", "value": 1.0})),
                tp=StopConfig.from_dict(data.get("tp", {"type": "PCT", "value": 2.0})),
                plan_ts=plan_ts,
                idempotency_key=data.get("idempotency_key", str(uuid.uuid4())),
                reasons=data.get("reasons", {}),
                policy_decision_id=data.get("policy_decision_id", ""),
                policy_phase_at_decision=data.get("policy_phase_at_decision", ""),
                cycle_index=int(data.get("cycle_index", 0)),
                input_fingerprint=data.get("input_fingerprint", ""),
            )
        except Exception:
            return None


def create_skip_plan(
    symbol: str,
    reason: str,
    reason_details: dict = None,
) -> TradePlanV1:
    """Create a SKIP trade plan."""
    return TradePlanV1(
        symbol=symbol,
        side=TradeSide.LONG,
        decision=TradeDecision.SKIP,
        notional_usdt=0,
        sl=StopConfig(type=StopType.PCT, value=0),
        tp=StopConfig(type=StopType.PCT, value=0),
        reasons={"skip_reason": reason, **(reason_details or {})},
    )


def create_locked_plan(symbol: str, lock_reason: str) -> TradePlanV1:
    """Create a SKIP plan due to trade lock."""
    return create_skip_plan(
        symbol=symbol,
        reason="TRADE_LOCKED",
        reason_details={"lock_reason": lock_reason},
    )
