"""
Pool Order Intents V1
=====================

Order intent models for pool execution.
"""
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def generate_order_key(stage: str, run_id: str, action: str, symbol: str, 
                       timeframe: Optional[str], bundle_id: Optional[str], src: str) -> str:
    """Generate deterministic idempotency key."""
    raw = f"{stage}|{run_id}|{action}|{symbol}|{timeframe or ''}|{bundle_id or ''}|{src}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]

def generate_intent_id(order_key: str) -> str:
    """Generate deterministic intent ID from order key."""
    return hashlib.sha1(order_key.encode()).hexdigest()[:16]

@dataclass
class PoolOrderIntentV1:
    """Single order intent."""
    intent_id: str
    order_key: str
    stage: str
    run_id: str
    action: str  # "OPEN_POSITION"|"CLOSE_POSITION"
    symbol: str
    timeframe: Optional[str]
    bundle_id: Optional[str]
    src: str  # "SELECTION"|"REPLACEMENT_PLAN"
    notional: float
    mode: str  # "MARKET_SIM"
    policy_spec: Optional[Dict[str, Any]]
    reason: str  # "OK"|"REPLACEMENT_CLOSE"|"REPLACEMENT_OPEN"|"BLOCKED_BY_COURT"
    created_ts_iso: str
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "order_key": self.order_key,
            "stage": self.stage,
            "run_id": self.run_id,
            "action": self.action,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bundle_id": self.bundle_id,
            "src": self.src,
            "notional": self.notional,
            "mode": self.mode,
            "policy_spec": self.policy_spec,
            "reason": self.reason,
            "created_ts_iso": self.created_ts_iso,
            "meta": self.meta
        }

@dataclass
class PoolOrderIntentsReportV1:
    """Order intents report."""
    run_id: str
    stage: str
    engine_version: str
    data_fingerprint: str
    config_signature: str
    built_ts_iso: str
    court_verdict: str  # "PASS"|"IMPROVE"|"FAIL"
    intents_total: int
    intents_open: int
    intents_close: int
    intents: List[PoolOrderIntentV1]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "stage": self.stage,
            "engine_version": self.engine_version,
            "data_fingerprint": self.data_fingerprint,
            "config_signature": self.config_signature,
            "built_ts_iso": self.built_ts_iso,
            "court_verdict": self.court_verdict,
            "intents_total": self.intents_total,
            "intents_open": self.intents_open,
            "intents_close": self.intents_close,
            "intents": [i.to_dict() for i in self.intents]
        }
