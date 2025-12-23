"""
Pool Risk Limiter V1
====================

Global + Per-Coin notional caps with deterministic trimming.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from collections import defaultdict

# Defaults
DEFAULT_GLOBAL_NOTIONAL_CAP = 2000.0
DEFAULT_PER_COIN_NOTIONAL_CAP = 300.0
DEFAULT_NOTIONAL_PER_TRADE = 100.0

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class RiskLimitResult:
    """Result of risk limit application."""
    allowed: List[Dict[str, Any]]
    blocked: List[Dict[str, Any]]
    blocked_reasons_count: Dict[str, int]
    global_notional_used: float
    per_coin_notional: Dict[str, float]

@dataclass
class RiskReportV2:
    """Risk Report V2 with detailed blocking info."""
    version: str
    run_id: str
    stage: str
    built_ts_iso: str
    kill_switch: Dict[str, Any]
    limits: Dict[str, float]
    portfolio: Dict[str, Any]
    planned: Dict[str, Any]
    allowed_count: int
    blocked_count: int
    blocked_reasons_count: Dict[str, int]
    blocked: List[Dict[str, Any]]
    allowed: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "run_id": self.run_id,
            "stage": self.stage,
            "built_ts_iso": self.built_ts_iso,
            "kill_switch": self.kill_switch,
            "limits": self.limits,
            "portfolio": self.portfolio,
            "planned": self.planned,
            "allowed_count": self.allowed_count,
            "blocked_count": self.blocked_count,
            "blocked_reasons_count": self.blocked_reasons_count,
            "blocked": self.blocked,
            "allowed": self.allowed
        }

def apply_limits(
    selected_intents: List[Dict[str, Any]],
    portfolio_open_notional: float = 0.0,
    coin_open_notional: Dict[str, float] = None,
    global_notional_cap: float = DEFAULT_GLOBAL_NOTIONAL_CAP,
    per_coin_notional_cap: float = DEFAULT_PER_COIN_NOTIONAL_CAP,
    kill_switch_triggered: bool = False
) -> RiskLimitResult:
    """
    Apply risk limits with deterministic trimming.
    
    Args:
        selected_intents: List of intent dicts with rank_score, intent_id, symbol, notional
        portfolio_open_notional: Current open notional from portfolio
        coin_open_notional: Per-coin open notional {symbol: notional}
        global_notional_cap: Global cap
        per_coin_notional_cap: Per-coin cap
        kill_switch_triggered: Kill switch status
        
    Returns:
        RiskLimitResult
    """
    if coin_open_notional is None:
        coin_open_notional = {}
    
    allowed = []
    blocked = []
    blocked_reasons = defaultdict(int)
    
    # Kill switch blocks all
    if kill_switch_triggered:
        for intent in selected_intents:
            blocked.append({**intent, "reason": "KILL_SWITCH"})
            blocked_reasons["KILL_SWITCH"] += 1
        return RiskLimitResult(
            allowed=[],
            blocked=blocked,
            blocked_reasons_count=dict(blocked_reasons),
            global_notional_used=portfolio_open_notional,
            per_coin_notional=coin_open_notional.copy()
        )
    
    # Step 1: Check global cap overflow and trim weakest
    total_planned = sum(i.get("notional", DEFAULT_NOTIONAL_PER_TRADE) for i in selected_intents)
    room_for_new = max(0, global_notional_cap - portfolio_open_notional)
    
    if total_planned > room_for_new:
        # Need to trim - sort by rank_score ASC (weakest first), then intent_id for determinism
        sorted_for_trim = sorted(selected_intents, key=lambda x: (x.get("rank_score", 0), x.get("intent_id", "")))
        overflow = total_planned - room_for_new
        
        global_blocked_ids = set()
        for intent in sorted_for_trim:
            if overflow <= 0:
                break
            notional = intent.get("notional", DEFAULT_NOTIONAL_PER_TRADE)
            global_blocked_ids.add(intent.get("intent_id"))
            overflow -= notional
        
        # Split into allowed_candidates and global_blocked
        allowed_candidates = [i for i in selected_intents if i.get("intent_id") not in global_blocked_ids]
        for intent in selected_intents:
            if intent.get("intent_id") in global_blocked_ids:
                blocked.append({**intent, "reason": "GLOBAL_NOTIONAL_CAP"})
                blocked_reasons["GLOBAL_NOTIONAL_CAP"] += 1
    else:
        allowed_candidates = list(selected_intents)
    
    # Step 2: Per-coin cap - protect strongest
    # Sort by rank_score DESC (strongest first), then intent_id for determinism
    sorted_for_coin = sorted(allowed_candidates, key=lambda x: (-x.get("rank_score", 0), x.get("intent_id", "")))
    
    current_coin_notional = coin_open_notional.copy()
    final_allowed = []
    
    for intent in sorted_for_coin:
        symbol = intent.get("symbol", "UNK")
        notional = intent.get("notional", DEFAULT_NOTIONAL_PER_TRADE)
        current = current_coin_notional.get(symbol, 0.0)
        
        if current + notional > per_coin_notional_cap:
            blocked.append({**intent, "reason": "PER_COIN_CAP"})
            blocked_reasons["PER_COIN_CAP"] += 1
        else:
            final_allowed.append(intent)
            current_coin_notional[symbol] = current + notional
    
    # Compute final global notional used
    allowed_notional = sum(i.get("notional", DEFAULT_NOTIONAL_PER_TRADE) for i in final_allowed)
    global_used = portfolio_open_notional + allowed_notional
    
    return RiskLimitResult(
        allowed=final_allowed,
        blocked=blocked,
        blocked_reasons_count=dict(blocked_reasons),
        global_notional_used=global_used,
        per_coin_notional=current_coin_notional
    )

def build_risk_report_v2(
    run_id: str,
    stage: str,
    selected_intents: List[Dict[str, Any]],
    limit_result: RiskLimitResult,
    portfolio_open_notional: float,
    portfolio_open_now: int,
    global_notional_cap: float,
    per_coin_notional_cap: float,
    kill_switch: Dict[str, Any] = None
) -> RiskReportV2:
    """Build Risk Report V2."""
    planned_notional = sum(i.get("notional", DEFAULT_NOTIONAL_PER_TRADE) for i in selected_intents)
    
    return RiskReportV2(
        version="pool_risk_report_v2",
        run_id=run_id,
        stage=stage,
        built_ts_iso=now_iso(),
        kill_switch=kill_switch or {"triggered": False},
        limits={
            "global_notional_cap": global_notional_cap,
            "per_coin_notional_cap": per_coin_notional_cap
        },
        portfolio={
            "open_now": portfolio_open_now,
            "notional_open": portfolio_open_notional
        },
        planned={
            "selected_count": len(selected_intents),
            "planned_notional": planned_notional
        },
        allowed_count=len(limit_result.allowed),
        blocked_count=len(limit_result.blocked),
        blocked_reasons_count=limit_result.blocked_reasons_count,
        blocked=limit_result.blocked,
        allowed=limit_result.allowed
    )
