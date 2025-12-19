# Tezaver Bulut - Cycle Timeline Schema V1
"""
Schema for Cycle Forensics Timeline.
Captures the state and flow of a single 15m cycle for debugging.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class CycleStageV1:
    """Represents a stage in the cycle (e.g., SCHED, DATA, SCAN)."""
    name: str  # SCHED, DATA, SCAN, DECIDE, EXEC, RISK
    status: str = "OK" # OK, SKIP, ERR, WARN
    duration_ms: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    
@dataclass
class CycleTimelineV1:
    """Complete timeline of a single cycle."""
    cycle_index: int
    cycle_ts: datetime
    
    stages: List[CycleStageV1] = field(default_factory=list)
    
    # P3: Strict Timing
    drift_ms: int = 0
    deduped: bool = False
    dedupe_reason: Optional[str] = None
    expected_close_ts: Optional[datetime] = None
    run_started_ts: Optional[datetime] = None
    
    # Source References (e.g. decision IDs, event IDs)
    source_refs: Dict[str, str] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "cycle_index": self.cycle_index,
            "cycle_ts": self.cycle_ts.isoformat(),
            "drift_ms": self.drift_ms,
            "deduped": self.deduped,
            "dedupe_reason": self.dedupe_reason,
            "expected_close_ts": self.expected_close_ts.isoformat() if self.expected_close_ts else None,
            "run_started_ts": self.run_started_ts.isoformat() if self.run_started_ts else None,
            "stages": [
                {
                    "name": s.name,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "details": s.details
                }
                for s in self.stages
            ],
            "source_refs": self.source_refs,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'CycleTimelineV1':
        inst = cls(
            cycle_index=data["cycle_index"],
            cycle_ts=datetime.fromisoformat(data["cycle_ts"])
        )
        inst.drift_ms = data.get("drift_ms", 0)
        inst.deduped = data.get("deduped", False)
        inst.dedupe_reason = data.get("dedupe_reason")
        inst.expected_close_ts = datetime.fromisoformat(data["expected_close_ts"]) if data.get("expected_close_ts") else None
        inst.run_started_ts = datetime.fromisoformat(data["run_started_ts"]) if data.get("run_started_ts") else None
        
        inst.source_refs = data.get("source_refs", {})
        inst.created_at = datetime.fromisoformat(data.get("created_at", datetime.now().isoformat()))
        
        for s_data in data.get("stages", []):
            inst.stages.append(CycleStageV1(
                name=s_data["name"],
                status=s_data.get("status", "OK"),
                duration_ms=s_data.get("duration_ms", 0),
                details=s_data.get("details", {})
            ))
            
        return inst
