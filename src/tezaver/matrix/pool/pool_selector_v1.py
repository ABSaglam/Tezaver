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

STORY_SCORE_BONUS = 50.0 # High priority for narrative-driven story packs

def compute_rank_score(intent: TradeIntentV1) -> float:
    """
    Compute ranking score for an intent.
    Score = QC Score + Tier Bonus
    """
    base_score = float(intent.qc_score or 0)
    tier_bonus = TIER_SCORE_BONUS.get(intent.tier, 0.0)
    
    # Story/Narrative Bonus
    story_bonus = 0.0
    if intent.scenario_id and intent.scenario_id != "SCENARIO_NEUTRAL":
        story_bonus = STORY_SCORE_BONUS
        
    return base_score + tier_bonus + story_bonus

from tezaver.core.stages import (
    STAGE_CANDIDATE, STAGE_SNIPER_PASSED, STAGE_LIVE_CERTIFIED, STAGE_DEMOTED
)

def select_topk(
    intents_ok: List[TradeIntentV1], 
    k: int,
    engine_stage: str = "WAR"
) -> Tuple[List[PoolSelectionItemV1], List[Dict[str, str]]]:
    """
    Deterministically select Top-K intents with Stage-based Certification Filtering.
    
    Filtering Rules (3-Stage Hierarchy):
    - LIVE Stage: Requires STAGE_LIVE_CERTIFIED.
    - WAR Stage: Requires STAGE_SNIPER_PASSED (or LIVE_CERTIFIED).
    - SNIPER Stage: Accepts STAGE_CANDIDATE (and above).
    
    Sorting Rules:
    1. Rank Score (DESC)
    2. Intent ID (ASC) - Tie breaker
    """
    if k <= 0:
        skipped = [{"intent_id": i.intent_id, "reason": "SKIPPED_OVERFLOW"} for i in intents_ok]
        return [], skipped

    # 1. Component Filter: Stage-based certification
    eligible_intents = []
    skipped_certification = []
    
    stage = engine_stage.upper()
    
    for i in intents_ok:
        cert = i.bundle_certification
        is_live_ready = (cert == STAGE_LIVE_CERTIFIED)
        is_war_ready = (cert in [STAGE_SNIPER_PASSED, STAGE_LIVE_CERTIFIED])
        
        # Rule 1: LIVE Stage -> Must be Live Certified
        if stage == "LIVE" and not is_live_ready:
            skipped_certification.append({"intent_id": i.intent_id, "reason": "SKIPPED_NOT_LIVE_READY"})
            continue
            
        # Rule 2: WAR Stage -> Must be Sniper Passed (or already Live Certified)
        if stage == "WAR" and not is_war_ready:
            # Note: Candidates are NOT allowed in WAR anymore. They must pass Sniper first.
            skipped_certification.append({"intent_id": i.intent_id, "reason": "SKIPPED_NOT_SNIPER_PASSED"})
            continue
            
        # Rule 3: SNIPER Stage -> Allows Candidates (Optimization Loop)
        # Any demoted bundle is generally skipped unless we have a 'retrain' logic
        if cert == STAGE_DEMOTED:
             skipped_certification.append({"intent_id": i.intent_id, "reason": "SKIPPED_DEMOTED"})
             continue
            
        eligible_intents.append(i)

    # 2. Transform to selectable items with score
    candidates = []
    for i in eligible_intents:
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
            proposed_notional=i.proposed_notional,
            rank_score=score,
            rank_reason="qc+tier+story",
            scenario_id=i.scenario_id,
            bundle_certification=i.bundle_certification
        )
        candidates.append(item)
        
    # 3. Sort Deterministically
    candidates.sort(key=lambda x: (-x.rank_score, x.intent_id))
    
    # 4. Slice
    selected = candidates[:k]
    overflow = candidates[k:]
    
    skipped_overflow = [{"intent_id": x.intent_id, "reason": "SKIPPED_OVERFLOW"} for x in overflow]
    
    # Combine skips
    all_skipped = skipped_certification + skipped_overflow
    
    return selected, all_skipped
