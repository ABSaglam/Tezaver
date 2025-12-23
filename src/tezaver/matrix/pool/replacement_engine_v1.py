"""
Replacement Engine V1
=====================

Deterministic replacement logic for Phase 3B.
Suggests replacing weak positions with better intents when capacity=0.
"""
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from tezaver.matrix.pool.pool_models_v1 import (
    PoolReplacementCandidateV1,
    PoolReplacementReportV1,
    PoolSelectionItemV1
)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# Tier bonus for position scoring
TIER_SCORE_BONUS = {
    "DIAMOND": 30.0,
    "GOLD": 20.0,
    "SILVER": 10.0,
    "BRONZE": 5.0,
    None: 0.0,
    "UNKNOWN": 0.0
}

def compute_pos_score(pos: Dict[str, Any]) -> float:
    """Compute score for a position (deterministic)."""
    qc = float(pos.get("qc_score", 0) or 0)
    tier = pos.get("tier")
    tier_bonus = TIER_SCORE_BONUS.get(tier, 0.0)
    return qc + tier_bonus

def find_worst_position(positions: List[Dict[str, Any]]) -> Tuple[Optional[Dict[str, Any]], float]:
    """
    Find the worst position by score.
    Tie-break: pos_id ASC (deterministic).
    
    Returns:
        (worst_position, worst_score)
    """
    if not positions:
        return None, 0.0
    
    scored = [(compute_pos_score(p), p.get("pos_id", p.get("symbol", "UNK")), p) for p in positions]
    # Sort by score ASC, then pos_id ASC
    scored.sort(key=lambda x: (x[0], x[1]))
    
    worst = scored[0]
    return worst[2], worst[0]

def find_best_intent(intents: List[PoolSelectionItemV1]) -> Tuple[Optional[PoolSelectionItemV1], float]:
    """
    Find the best intent by rank_score.
    Tie-break: intent_id ASC (deterministic).
    
    Returns:
        (best_intent, best_score)
    """
    if not intents:
        return None, 0.0
    
    # Sort by rank_score DESC, intent_id ASC
    sorted_intents = sorted(intents, key=lambda x: (-x.rank_score, x.intent_id))
    best = sorted_intents[0]
    return best, best.rank_score

def evaluate_replacement(
    run_id: str,
    stage: str,
    trace_ctx: Dict[str, str],
    open_positions: List[Dict[str, Any]],
    selected_intents: List[PoolSelectionItemV1],
    capacity: int,
    open_now: int,
    max_open_positions: int,
    reconcile_verdict: str,
    kill_switch_triggered: bool = False,
    risk_limiter_triggered: bool = False,
    config: Optional[Dict[str, Any]] = None
) -> PoolReplacementReportV1:
    """
    Evaluate replacement possibility.
    
    Args:
        run_id: Run ID
        stage: Run stage
        trace_ctx: Context for determinism
        open_positions: Current open positions
        selected_intents: Selected intents from Phase 2B
        capacity: Available capacity (from selection)
        open_now: Current open count
        max_open_positions: Max positions limit
        reconcile_verdict: Restart reconcile verdict
        kill_switch_triggered: Kill switch state
        risk_limiter_triggered: Risk limiter state
        config: {"replacement_enabled": bool, "replacement_min_delta": float, "replacement_min_rank": float}
        
    Returns:
        PoolReplacementReportV1
    """
    cfg = config or {}
    enabled = cfg.get("replacement_enabled", False)
    min_delta = cfg.get("replacement_min_delta", 15.0)
    min_rank = cfg.get("replacement_min_rank", 90.0)
    
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    
    base_report = {
        "run_id": run_id,
        "stage": stage,
        "engine_version": ev,
        "data_fingerprint": df,
        "config_signature": cs,
        "built_ts_iso": now_iso(),
        "enabled": enabled,
        "capacity": capacity,
        "open_now": open_now,
        "max_open_positions": max_open_positions,
        "considered_intents": len(selected_intents)
    }
    
    # 1. Check if disabled
    if not enabled:
        return PoolReplacementReportV1(**base_report, verdict="SKIPPED", skip_reason="DISABLED", candidate=None)
    
    # 2. Check capacity available
    if capacity > 0:
        return PoolReplacementReportV1(**base_report, verdict="SKIPPED", skip_reason="CAPACITY_AVAILABLE", candidate=None)
    
    # 3. Check drift
    if reconcile_verdict != "OK":
        return PoolReplacementReportV1(**base_report, verdict="SKIPPED", skip_reason="DRIFT", candidate=None)
    
    # 4. Check kill switch / risk limiter
    if kill_switch_triggered:
        return PoolReplacementReportV1(**base_report, verdict="SKIPPED", skip_reason="KILL_SWITCH", candidate=None)
    if risk_limiter_triggered:
        return PoolReplacementReportV1(**base_report, verdict="SKIPPED", skip_reason="GLOBAL_RISK_LIMIT", candidate=None)
    
    # 5. Find worst position
    worst_pos, worst_score = find_worst_position(open_positions)
    if not worst_pos:
        return PoolReplacementReportV1(**base_report, verdict="SKIPPED", skip_reason="NO_POSITIONS", candidate=None)
    
    # 6. Find best intent
    best_intent, best_score = find_best_intent(selected_intents)
    if not best_intent:
        return PoolReplacementReportV1(**base_report, verdict="SKIPPED", skip_reason="NO_INTENTS", candidate=None)
    
    # Check min rank threshold
    if best_score < min_rank:
        return PoolReplacementReportV1(**base_report, verdict="SKIPPED", skip_reason="NO_BETTER_THAN_WORST", candidate=None)
    
    # 7. Compare
    delta = best_score - worst_score
    if delta < min_delta:
        return PoolReplacementReportV1(**base_report, verdict="SKIPPED", skip_reason="NO_BETTER_THAN_WORST", candidate=None)
    
    # 8. Create candidate
    candidate = PoolReplacementCandidateV1(
        replace_out_pos_id=worst_pos.get("pos_id", worst_pos.get("symbol", "UNK")),
        replace_out_symbol=worst_pos.get("symbol", "UNK"),
        replace_out_timeframe=worst_pos.get("timeframe"),
        replace_out_score=worst_score,
        replace_in_intent_id=best_intent.intent_id,
        replace_in_symbol=best_intent.symbol,
        replace_in_timeframe=best_intent.timeframe,
        replace_in_bundle_id=best_intent.bundle_id,
        replace_in_rank_score=best_score,
        delta_score=delta,
        reason="BONUS_BETTER_THAN_WORST",
        requires_human_confirm=True
    )
    
    return PoolReplacementReportV1(**base_report, verdict="SUGGESTED", skip_reason=None, candidate=candidate)
