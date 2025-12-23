"""
Pool Selector V1
================

Deterministic selection logic for Phase 2B.
Prioritizes intents based on QC Score and Tier.
"""
from typing import List, Tuple, Dict, Any, Optional
from tezaver.matrix.pool.pool_models_v1 import (
    TradeIntentV1, 
    PoolSelectionItemV1
)

# Configuration for score boost
TIER_SCORE_BONUS = {
    "DIAMOND": 30.0,
    "GOLD": 20.0,
    "SILVER": 10.0,
    "BRONZE": 5.0,
    None: 0.0,
    "UNKNOWN": 0.0
}

def compute_rank_score(intent: TradeIntentV1) -> float:
    """
    Compute ranking score for an intent.
    Score = QC Score + Tier Bonus
    """
    base_score = float(intent.qc_score or 0)
    tier_bonus = TIER_SCORE_BONUS.get(intent.tier, 0.0)
    return base_score + tier_bonus

def select_topk(
    intents_ok: List[TradeIntentV1], 
    k: int
) -> Tuple[List[PoolSelectionItemV1], List[Dict[str, str]]]:
    """
    Deterministically select Top-K intents.
    
    Sorting Rules:
    1. Rank Score (DESC)
    2. Intent ID (ASC) - Tie breaker
    
    Args:
        intents_ok: List of eligible intents (reason="OK")
        k: Capacity limit
        
    Returns:
        (selected_items, skipped_overflow_list)
    """
    if k <= 0:
        # No capacity, skip all
        skipped = [{"intent_id": i.intent_id, "reason": "SKIPPED_OVERFLOW"} for i in intents_ok]
        return [], skipped

    # 1. Transform to selectable items with score
    candidates = []
    for i in intents_ok:
        score = compute_rank_score(i)
        item = PoolSelectionItemV1(
            intent_id=i.intent_id,
            symbol=i.symbol,
            timeframe=i.timeframe,
            bundle_id=i.bundle_id,
            qc_score=i.qc_score,
            tier=i.tier,
            trigger_type=i.trigger_type,
            exit_policy=i.exit_policy,
            rank_score=score,
            rank_reason="qc+tier"
        )
        candidates.append(item)
        
    # 2. Sort Deterministically
    # -score for DESC, intent_id for ASC
    candidates.sort(key=lambda x: (-x.rank_score, x.intent_id))
    
    # 3. Slice
    selected = candidates[:k]
    overflow = candidates[k:]
    
    skipped_overflow = [{"intent_id": x.intent_id, "reason": "SKIPPED_OVERFLOW"} for x in overflow]
    
    return selected, skipped_overflow
