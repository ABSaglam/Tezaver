"""
Pool Risk Engine V1
====================

Deterministic risk evaluation for Phase 2C.
Checks policy, kill switch, risk limiter, and global notional limits.
"""
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from tezaver.matrix.pool.pool_models_v1 import (
    PoolSelectionItemV1,
    PoolRiskItemV1,
    PoolRiskReportV1
)
from tezaver.matrix.pool.pool_reports_v1 import now_iso
from tezaver.matrix.bundles.bundle_registry import BundleRegistry

# Default configuration
DEFAULT_MAX_TOTAL_NOTIONAL = 10000.0
DEFAULT_PER_COIN_MAX_NOTIONAL = 1000.0
DEFAULT_NOTIONAL = 100.0


def extract_stop_info(policy_spec: Optional[Dict[str, Any]]) -> Tuple[str, Optional[float]]:
    """
    Extract stop type and value from policy_spec.
    
    Returns:
        (stop_type, stop_value)
    """
    if not policy_spec:
        return ("NONE", None)
        
    exit_policy = policy_spec.get("exit_policy", "NONE")
    params = policy_spec.get("params", {})
    
    if exit_policy == "ATR":
        return ("ATR", params.get("atr_mult", 2.0))
    elif exit_policy == "FIXED":
        return ("FIXED", params.get("stop_pct", 0.05))
    elif exit_policy == "TRAILING":
        return ("TRAILING", params.get("trailing_pct", 0.05))
    else:
        return ("NONE", None)


def extract_notional(policy_spec: Optional[Dict[str, Any]], default: float = DEFAULT_NOTIONAL) -> float:
    """Extract proposed notional from policy_spec params or use default."""
    if policy_spec and "params" in policy_spec:
        return float(policy_spec["params"].get("notional", default))
    return default


def evaluate_risk(
    selected_items: List[PoolSelectionItemV1],
    registry: BundleRegistry,
    global_limits: Optional[Dict[str, Any]] = None,
    kill_switch_triggered: bool = False,
    risk_limiter_triggered: bool = False
) -> Tuple[List[PoolRiskItemV1], Dict[str, int]]:
    """
    Evaluate risk for each selected intent.
    
    Args:
        selected_items: List of selected intents from Phase 2B
        registry: Bundle registry for manifest lookup
        global_limits: {"max_total_notional": float, "per_coin_max_notional": float}
        kill_switch_triggered: If True, block all
        risk_limiter_triggered: If True, block all
        
    Returns:
        (risk_items, blocked_reasons_count)
    """
    limits = global_limits or {
        "max_total_notional": DEFAULT_MAX_TOTAL_NOTIONAL,
        "per_coin_max_notional": DEFAULT_PER_COIN_MAX_NOTIONAL
    }
    
    max_total = limits.get("max_total_notional", DEFAULT_MAX_TOTAL_NOTIONAL)
    per_coin_max = limits.get("per_coin_max_notional", DEFAULT_PER_COIN_MAX_NOTIONAL)
    
    risk_items: List[PoolRiskItemV1] = []
    blocked_reasons: Dict[str, int] = defaultdict(int)
    
    # Track cumulative notional for global limit
    cumulative_notional = 0.0
    
    # Sort by rank_score DESC for deterministic trimming (highest score first)
    sorted_items = sorted(selected_items, key=lambda x: -x.rank_score)
    
    for item in sorted_items:
        # 1. Get bundle manifest
        bundle = registry.get(item.bundle_id)
        policy_spec = None
        if bundle and bundle.manifest:
            policy_spec = bundle.manifest.policy_spec_v1
            
        # 2. Extract stop info
        stop_type, stop_value = extract_stop_info(policy_spec)
        
        # 3. Extract notional (clamped)
        proposed_notional = extract_notional(policy_spec)
        proposed_notional = min(proposed_notional, per_coin_max)
        
        # 4. Compute risk_units (simple: notional/1000)
        risk_units = proposed_notional / 1000.0
        
        # 5. Determine verdict
        verdict = "ALLOW"
        block_reason = None
        risk_flags: List[str] = []
        
        # Check Kill Switch
        if kill_switch_triggered:
            verdict = "BLOCK"
            block_reason = "KILL_SWITCH"
        # Check Risk Limiter
        elif risk_limiter_triggered:
            verdict = "BLOCK"
            block_reason = "GLOBAL_RISK_LIMIT"
        # Check Missing Policy
        elif policy_spec is None:
            verdict = "BLOCK"
            block_reason = "MISSING_POLICY"
        # Check Global Notional Limit
        elif cumulative_notional + proposed_notional > max_total:
            verdict = "BLOCK"
            block_reason = "GLOBAL_NOTIONAL_LIMIT"
        
        if verdict == "ALLOW":
            cumulative_notional += proposed_notional
        else:
            blocked_reasons[block_reason] += 1
            
        risk_item = PoolRiskItemV1(
            intent_id=item.intent_id,
            symbol=item.symbol,
            timeframe=item.timeframe,
            bundle_id=item.bundle_id,
            qc_score=item.qc_score,
            tier=item.tier,
            proposed_notional=proposed_notional,
            risk_units=risk_units,
            stop_type=stop_type,
            stop_value=stop_value,
            risk_flags=risk_flags,
            verdict=verdict,
            block_reason=block_reason
        )
        risk_items.append(risk_item)
        
    return risk_items, dict(blocked_reasons)
