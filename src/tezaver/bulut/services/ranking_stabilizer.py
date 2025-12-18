# Tezaver Bulut - Ranking Stabilizer
"""
Stabilizes ranking results with hysteresis and stickiness.
"""

from typing import List, Dict, Set
from datetime import datetime, timedelta

from tezaver.bulut.schemas.ranking_snapshot_v1 import CandidateScore


class RankingStabilizer:
    """
    Stabilizes ranking list to prevent rapid flickering.
    
    Features:
    - Stickiness: Previous TopK candidates get a bonus to stay in list
    - Hysteresis: Prevents items hovering near threshold from bouncing in/out
    """
    
    def __init__(self):
        self._history: Dict[str, datetime] = {} # symbol -> last_seen_in_topk_ts
        
    def stabilize(
        self,
        cycle_ts: datetime,
        raw_candidates: List[CandidateScore],
        topk: int,
        threshold: float,
        ttl_cycles: int = 2,
        bonus: float = 3.0,
        cycle_interval_min: int = 15
    ) -> List[CandidateScore]:
        """
        Apply stabilization rules.
        
        1. Base Filter: Must meet minimum threshold (raw score)
        2. Bonus: If symbol was in TopK recently (within ttl), add bonus to score
        3. Re-sort and take TopK
        """
        
        # 1. Base Filter & Apply Bonus
        processed_candidates = []
        current_topk_set = set()
        
        expiration_delta = timedelta(minutes=ttl_cycles * cycle_interval_min * 1.5) # slightly generous buffer
        
        for cand in raw_candidates:
            # Must meet hard threshold first - safety
            if cand.score < threshold:
                continue
                
            final_score = cand.score
            
            # Check history
            last_seen = self._history.get(cand.symbol)
            if last_seen and (cycle_ts - last_seen) <= expiration_delta:
                final_score += bonus
                cand.flags.append("STABLE_BONUS")
            elif last_seen:
                # Expired
                del self._history[cand.symbol]
            
            # Create new object with stabilized score to preserve raw inputs elsewhere if needed
            # Or just update inplace for simplicity in this pipeline context
            cand.score = min(100.0, final_score) # Clamp
            processed_candidates.append(cand)
            
        # 2. Re-sort
        processed_candidates.sort(key=lambda x: x.score, reverse=True)
        
        # 3. TopK Limit
        shortlist = processed_candidates[:topk]
        
        # Update history with new shortlist
        for cand in shortlist:
            self._history[cand.symbol] = cycle_ts
            
        return shortlist
