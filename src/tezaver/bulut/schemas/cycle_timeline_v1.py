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
    
    # Source References (e.g. decision IDs, event IDs)
    source_refs: Dict[str, str] = field(default_factory=dict)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "cycle_index": self.cycle_index,
            "cycle_ts": self.cycle_ts.isoformat(),
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
