# Tezaver Bulut - Scanner Engine
"""
Scans symbol universe and produces RankingSnapshot.
Version: v0.03 (Full Logic)
"""

import time
from datetime import datetime, timezone
from typing import Optional, List, Dict

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.schemas.ranking_snapshot_v1 import (
    RankingSnapshotV1,
    CandidateScore,
)
from tezaver.bulut.services.pattern_pack_loader import PatternPackLoader
from tezaver.bulut.services.bars_15m_store import Bars15mStore
from tezaver.bulut.services.timeframe_aggregator import TimeframeAggregator
from tezaver.bulut.services.ranking_stabilizer import RankingStabilizer


class Scanner:
    """
    Universe scanner for Tezaver Bulut.
    
    Flow:
    1. Filter Universe
    2. Derivation (1h/4h)
    3. Component Scoring (Pattern, Trend, Risk)
    4. Stabilization
    5. Snapshot Generation
    """
    
    def __init__(
        self,
        config: BulutConfig,
        pattern_loader: Optional[PatternPackLoader] = None,
        universe: Optional[List[str]] = None,
        bars_store: Optional[Bars15mStore] = None,
        stabilizer: Optional[RankingStabilizer] = None,
    ):
        self._config = config
        self._pattern_loader = pattern_loader
        self._symbols = universe or []
        self._bars_store = bars_store
        self._stabilizer = stabilizer
    
    def scan(self) -> RankingSnapshotV1:
        start_time = time.time()
        
        candidates = []
        current_symbols = self._symbols
        
        # --- Scanning Phase ---
        for symbol in current_symbols:
            candidate = self._analyze_symbol(symbol)
            candidates.append(candidate)
            
        # --- Stabilization Phase ---
        cycle_ts = datetime.now(timezone.utc)
        
        shortlist = []
        if self._stabilizer:
            shortlist = self._stabilizer.stabilize(
                cycle_ts=cycle_ts,
                raw_candidates=candidates,
                topk=self._config.scan_topk,
                threshold=self._config.scan_min_score,
                ttl_cycles=2,
                bonus=3.0
            )
        else:
            # Fallback simple sort/filter
            filtered = [c for c in candidates if c.score >= self._config.scan_min_score]
            filtered.sort(key=lambda x: x.score, reverse=True)
            shortlist = filtered[:self._config.scan_topk]

        # --- Snapshot Phase ---
        # Note: We must store FULL candidates list in snapshot generally? 
        # But for efficiency v1 usually stores shortlisted. 
        # Actually API routes usually serve shortlist. 
        # RankingSnapshotV1.candidates holds ALL scored items or just top items?
        # Usually it holds all significant ones. Let's store raw_candidates (unfiltered) 
        # but the properties .shortlist will filter them again?
        # No, stabilize modifies scores (adds bonus). We should store stabilized list as candidates?
        # NO, Stabilizer logic needs persistent history. Returns the "winners".
        # Let's adhere to v0.01 spec: candidates list in snapshot holding scores.
        # We will populate candidates with `shortlist` for now to save space, 
        # or `candidates` as fully scored list (stabilized) but not cut by K?
        # Better: apply stabilization to ALL, then save ALL to snapshot, let snapshot.shortlist logic filter K.
        
        # Simpler approach matching requirements: "Raw candidate listesini RankingStabilizer’dan geçir, sonra snapshot üret."
        # This implies stabilizer returns the final list.
        # But stabilizer also cuts by TopK.
        
        snapshot = RankingSnapshotV1(
            cycle_ts=cycle_ts,
            base_tf=self._config.base_tf,
            derived_tfs=self._config.derived_tfs,
            universe_size=len(current_symbols),
            threshold=self._config.scan_min_score,
            topk=self._config.scan_topk,
            candidates=shortlist # We only store the "winners"
        )
        
        duration_ms = (time.time() - start_time) * 1000
        print(f"[SCANNER] Scanned {len(current_symbols)} symbols in {duration_ms:.1f}ms. Shortlist: {len(shortlist)}")
        
        return snapshot

    def _analyze_symbol(self, symbol: str) -> CandidateScore:
        flags = []
        
        # 1. Data & Derivation
        derived = {"1h": None, "4h": None}
        bars_15m = []
        
        if self._bars_store:
            bars_15m = self._bars_store.get_last_n_closed(symbol, 16)
            
            if len(bars_15m) < 16:
                flags.append("INSUFFICIENT_15M_BARS")
                
            derived = TimeframeAggregator.derive(symbol, bars_15m)
            if not derived["1h"]:
                flags.append("MISSING_1H")
            if not derived["4h"]:
                flags.append("MISSING_4H")
        
        # 2. Scoring Components
        
        # Pattern Score
        score_pattern = 0.0
        matched_patterns = []
        if self._pattern_loader:
            match_res = self._pattern_loader.match_symbol(symbol, "15m")
            score_pattern = match_res.get("score", 0.0) * 0.6 # Scaling to 60 point max for component
            matched_patterns = match_res.get("matches", [])
            
            if score_pattern > 0:
                flags.append("PATTERN_MATCH")
        
        # Trend Score
        score_trend = 0.0
        bar1h = derived.get("1h")
        if bar1h and bar1h.c > bar1h.o:
            score_trend += 10.0
            
        bar4h = derived.get("4h")
        if bar4h and bar4h.c > bar4h.o:
            score_trend += 15.0
            
        # Risk Score
        score_risk = 5.0 # Default bonus
        if len(bars_15m) >= 4:
            # Check volatility roughly
            # Avg body size last 4 bars
            recent = bars_15m[-4:]
            avg_body_pct = sum(abs(b.c - b.o) / b.c for b in recent) / 4.0
            if avg_body_pct > 0.03: # >3% volatility per 15m is high
                score_risk = -5.0
                flags.append("HIGH_VOLATILITY")
        
        # Total
        total_raw = score_pattern + score_trend + score_risk
        
        # Ensure pattern score scaling didn't break total logic
        # If Pattern gives 100, we scaled to 60.
        # Trend gives 25. Risk gives 5. Total 90. Fits in 0-100.
        
        total_clamped = max(0.0, min(100.0, total_raw))
        
        return CandidateScore(
            symbol=symbol,
            score=total_clamped,
            components={
                "pattern": score_pattern,
                "trend": score_trend,
                "risk": score_risk
            },
            flags=flags,
            matched_patterns=matched_patterns
        )


def run_scan(
    config: BulutConfig,
    pattern_loader: Optional[PatternPackLoader] = None,
    universe: Optional[List[str]] = None,
    bars_store: Optional[Bars15mStore] = None,
    stabilizer: Optional[RankingStabilizer] = None,
) -> RankingSnapshotV1:
    """Convenience function to run scanner."""
    scanner = Scanner(config, pattern_loader, universe, bars_store, stabilizer)
    return scanner.scan()
