# Tezaver Bulut - Ranking Snapshot Schema v1
"""
Schema definition for RankingSnapshot v1.

Output of each scan cycle with scored candidates.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


SCHEMA_VERSION = "ranking_snapshot_v1"


@dataclass
class CandidateScore:
    """Single candidate in ranking."""
    symbol: str
    score: float  # 0..100
    components: dict = field(default_factory=dict)  # e.g., {"pattern": 60, "trend": 15, "risk": 10}
    flags: list[str] = field(default_factory=list)  # e.g., ["HIGH_VOLUME", "PATTERN_MATCH"]
    
    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "score": round(self.score, 2),
            "components": self.components,
            "flags": self.flags,
        }


@dataclass
class RankingSnapshotV1:
    """
    Ranking Snapshot v1 Schema.
    
    Structure:
    {
        "schema": "ranking_snapshot_v1",
        "cycle_ts": "iso",
        "base_tf": "15m",
        "derived_tfs": ["1h", "4h"],
        "universe_size": 400,
        "threshold": 70,
        "topk": 20,
        "candidates": [...]
    }
    """
    cycle_ts: datetime
    base_tf: str
    derived_tfs: list[str]
    universe_size: int
    threshold: int
    topk: int
    candidates: list[CandidateScore] = field(default_factory=list)
    
    @property
    def schema(self) -> str:
        return SCHEMA_VERSION
    
    @property
    def shortlist(self) -> list[CandidateScore]:
        """Get candidates above threshold, limited to topk."""
        above_threshold = [c for c in self.candidates if c.score >= self.threshold]
        return sorted(above_threshold, key=lambda x: x.score, reverse=True)[:self.topk]
    
    @property
    def shortlist_symbols(self) -> list[str]:
        """Get symbols in shortlist."""
        return [c.symbol for c in self.shortlist]
    
    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "cycle_ts": self.cycle_ts.isoformat() if isinstance(self.cycle_ts, datetime) else self.cycle_ts,
            "base_tf": self.base_tf,
            "derived_tfs": self.derived_tfs,
            "universe_size": self.universe_size,
            "threshold": self.threshold,
            "topk": self.topk,
            "candidates": [c.to_dict() for c in self.candidates],
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Optional["RankingSnapshotV1"]:
        """Parse from dictionary."""
        if data.get("schema") != SCHEMA_VERSION:
            return None
        
        try:
            cycle_ts = data.get("cycle_ts", "")
            if isinstance(cycle_ts, str):
                cycle_ts = datetime.fromisoformat(cycle_ts.replace("Z", "+00:00"))
            
            candidates = [
                CandidateScore(
                    symbol=c.get("symbol", ""),
                    score=float(c.get("score", 0)),
                    components=c.get("components", {}),
                    flags=c.get("flags", []),
                )
                for c in data.get("candidates", [])
            ]
            
            return cls(
                cycle_ts=cycle_ts,
                base_tf=data.get("base_tf", "15m"),
                derived_tfs=data.get("derived_tfs", []),
                universe_size=data.get("universe_size", 0),
                threshold=data.get("threshold", 70),
                topk=data.get("topk", 20),
                candidates=candidates,
            )
        except Exception:
            return None


def create_empty_ranking(
    base_tf: str = "15m",
    derived_tfs: list[str] = None,
    threshold: int = 70,
    topk: int = 20,
) -> RankingSnapshotV1:
    """Create empty ranking snapshot."""
    return RankingSnapshotV1(
        cycle_ts=datetime.now(timezone.utc),
        base_tf=base_tf,
        derived_tfs=derived_tfs or ["1h", "4h"],
        universe_size=0,
        threshold=threshold,
        topk=topk,
        candidates=[],
    )
