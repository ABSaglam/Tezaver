"""
Foundry Data Models
===================

Data structures for QC reports and packaging metadata.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime


@dataclass
class QCReport:
    """
    Quality Control Report for a single annotation.
    
    Attributes:
        symbol: Trading pair symbol
        timeframe: Timeframe (15m, 1h, 4h)
        event_id: Unique event identifier
        qc_verdict: "PASS" or "FAIL"
        score: Quality score (0-100)
        fails: List of failure reasons
        warns: List of warning reasons
        created_at: Report generation timestamp (ISO)
        engine_version: QC engine version identifier
        pointers: File paths for traceability
    """
    symbol: str
    timeframe: str
    event_id: str
    qc_verdict: str  # "PASS" | "FAIL"
    score: int  # 0-100
    fails: List[str] = field(default_factory=list)
    warns: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    engine_version: str = "qc_gate_v1"
    pointers: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "QCReport":
        """Load from dictionary."""
        return QCReport(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            event_id=data["event_id"],
            qc_verdict=data["qc_verdict"],
            score=data["score"],
            fails=data.get("fails", []),
            warns=data.get("warns", []),
            created_at=data.get("created_at", ""),
            engine_version=data.get("engine_version", "qc_gate_v1"),
            pointers=data.get("pointers")
        )
