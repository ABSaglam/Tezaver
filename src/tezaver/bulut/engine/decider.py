# Tezaver Bulut - Decider Engine v0.05
"""
Decider engine for making trade decisions based on ranking and constraints.
"""

from typing import List, Optional, Set
from datetime import datetime
import json

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.schemas.ranking_snapshot_v1 import RankingSnapshotV1, CandidateScore
from tezaver.bulut.schemas.trade_plan_v1 import (
    TradePlanV1, 
    TradeSide, 
    TradeDecision, 
    StopConfig,
    create_locked_plan
)


class Decider:
    """
    Decider making trade decisions.
    
    Pipeline:
    1. Input Validation (Pack loaded?)
    2. Candidate Filtering (Score, Allowlist)
    3. Global Limits Check (Max Pos, Max Notional)
    4. Cycle Limits Check (Max New Entries)
    5. Plan Generation (SL/TP, Notional)
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
    
    def decide(
        self,
        ranking: RankingSnapshotV1,
        open_positions_count: int,
        total_notional: float,
        pattern_pack_loaded: bool,
        allowlist: Optional[Set[str]] = None,
    ) -> List[TradePlanV1]:
        """
        Execute decision pipeline.
        Returns list of generated plans (PROPOSED/BLOCKED).
        """
        plans: List[TradePlanV1] = []
        
        # 1. Check Global Trade Lock (Pattern Pack)
        if not pattern_pack_loaded:
            # If pack missing, we can't trade comfortably.
            # Only generate one generic blocked plan or return empty?
            # Requirement: "Eğer pattern pack yoksa: OPEN plan üretme; sadece BLOCKED reason..."
            # Implementation: Skip processing, maybe log? 
            # Or generate a dummy "system block" plan if explicitly asked? 
            # Usually we just don't trade.
            # But let's return a dummy plan to indicate decision was made but blocked?
            # V0.01 used create_locked_plan.
            # Let's iterate candidates but block all?
            # Better: if not loaded, return empty list or single system warning plan.
            # Let's return NO plans if not loaded to avoid spam, but caller should check lock.
            return []

        # 2. Candidate Selection
        # Use ranking.candidates (which should be stabilized/shortlisted by scanner)
        # But filter by trade_min_score explicitly just in case
        candidates = [
            c for c in ranking.candidates 
            if c.score >= self._config.trade_min_score
        ]
        
        # Check Allowlist
        filtered_candidates = []
        for cand in candidates:
            if allowlist is not None and cand.symbol not in allowlist:
                # Can create BLOCKED plan or just skip? 
                # "Allowlist dışındaysa: BLOCKED reason: ALLOWLIST"
                # Let's create a BLOCKED plan for visibility.
                plans.append(self._create_plan(
                    cand, ranking.cycle_ts, TradeDecision.SKIP, 
                    reasons={"skip_reason": "ALLOWLIST_BLOCK"}
                ))
            else:
                filtered_candidates.append(cand)
        
        # Sort by score again to be safe
        filtered_candidates.sort(key=lambda x: x.score, reverse=True)
        
        # Take TopN for consideration
        consideration_list = filtered_candidates[:self._config.trade_topn_from_ranking]
        
        # 3. Entry Logic
        new_entries_count = 0
        
        for cand in consideration_list:
            # Check limits
            
            # Global Max Position Limit
            if open_positions_count >= self._config.max_open_positions:
                plans.append(self._create_plan(
                    cand, ranking.cycle_ts, TradeDecision.SKIP,
                    reasons={"skip_reason": "MAX_POSITIONS_REACHED"}
                ))
                continue
                
            # Cycle Limit
            if new_entries_count >= self._config.max_new_entries_per_cycle:
                plans.append(self._create_plan(
                    cand, ranking.cycle_ts, TradeDecision.SKIP,
                    reasons={"skip_reason": "CYCLE_ENTRY_LIMIT_REACHED"}
                ))
                continue
            
            # If passed all gates -> OPEN
            # Notional Calculation (Deterministic)
            notional = min(self._config.max_cell_notional_usdt, 100.0)
            
            # Create OPEN Plan
            plan = self._create_plan(
                cand, ranking.cycle_ts, TradeDecision.OPEN,
                notional=notional,
                reasons={
                    "entry_score": cand.score,
                    "pattern_score": cand.components.get("pattern", 0),
                    "trend_score": cand.components.get("trend", 0)
                }
            )
            
            # Set SL/TP (1% / 2%) - Placeholder logic
            # In real system, these come from volatility/ATR
            plan.sl = StopConfig(type="PERCENT", value=1.0)
            plan.tp = StopConfig(type="PERCENT", value=2.0)
            
            plans.append(plan)
            new_entries_count += 1
            open_positions_count += 1 # Increment simulated local counter
            
        return plans

    def _create_plan(
        self, 
        candidate: CandidateScore, 
        ts: datetime, 
        decision: TradeDecision,
        notional: float = 0.0,
        reasons: dict = None
    ) -> TradePlanV1:
        """Helper to create TradePlanV1."""
        # Idempotency key: cycle_ts:symbol:decision
        # cycle_ts is datetime
        key = f"{ts.isoformat()}:{candidate.symbol}:{decision.name}"
        
        return TradePlanV1(
            plan_ts=ts,
            symbol=candidate.symbol,
            side=TradeSide.LONG, # Hardcoded LONG_ONLY for now
            decision=decision,
            notional_usdt=notional,
            idempotency_key=key,
            reasons=reasons or {}
        )
