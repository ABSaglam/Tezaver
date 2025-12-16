# Matrix V2 Telemetry Module
"""
Event logging and telemetry for Matrix V2.

Provides standardized event format for War Game and Live trading.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Protocol, List, Dict, Any, Optional, runtime_checkable

from .guardrail import GuardrailEnvironment


# =============================================================================
# Event Types
# =============================================================================

class MatrixEventType(str, Enum):
    """Type of Matrix event."""
    TICK_START = "TICK_START"
    TICK_END = "TICK_END"
    SIGNAL = "SIGNAL"
    DECISION = "DECISION"
    GUARDRAIL_V1 = "GUARDRAIL_V1"  # Classic position/loss limits
    GUARDRAIL_V2 = "GUARDRAIL_V2"  # Profile/risk_contract
    # Rally
    RALLY_DETECTED = "RALLY_DETECTED"
    
    # System
    ERROR = "ERROR"
    INFO = "INFO"


# =============================================================================
# Event Dataclass
# =============================================================================

@dataclass
class MatrixEvent:
    """
    Single event in the Matrix diary/telemetry.
    
    Used by both War Game and Live for unified logging.
    """
    event_type: MatrixEventType
    symbol: str = ""
    timeframe: str = ""
    profile_id: Optional[str] = None
    environment: GuardrailEnvironment = GuardrailEnvironment.WARGAME
    ts: Optional[datetime] = None
    tick_index: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        d = asdict(self)
        # Convert enum values to strings
        d["event_type"] = self.event_type.value
        d["environment"] = self.environment.value
        # Convert datetime to ISO string
        if self.ts:
            d["ts"] = self.ts.isoformat()
        return d


# =============================================================================
# Event Sink Protocol
# =============================================================================

@runtime_checkable
class IMatrixEventSink(Protocol):
    """Protocol for event logging sinks."""
    
    def log(self, event: MatrixEvent) -> None:
        """Log a single event."""
        ...
    
    def get_events(self) -> List[MatrixEvent]:
        """Get all logged events (if supported)."""
        ...


# =============================================================================
# In-Memory Event Sink
# =============================================================================

class InMemoryEventSink:
    """
    In-memory event sink for War Game and testing.
    
    Stores events in a list for later analysis.
    """
    
    def __init__(self) -> None:
        self._events: List[MatrixEvent] = []
    
    def log(self, event: MatrixEvent) -> None:
        """Append event to internal list."""
        self._events.append(event)
    
    def get_events(self) -> List[MatrixEvent]:
        """Return copy of events list."""
        return list(self._events)
    
    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()
    
    def __len__(self) -> int:
        return len(self._events)


# =============================================================================
# JSON File Event Sink (NDJSON)
# =============================================================================

class JsonFileEventSink:
    """
    NDJSON file event sink.
    
    Appends each event as a JSON line to the specified file.
    """
    
    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._events: List[MatrixEvent] = []  # Also keep in memory for get_events
    
    def log(self, event: MatrixEvent) -> None:
        """Append event to file as NDJSON."""
        self._events.append(event)
        with open(self._path, "a", encoding="utf-8") as f:
            json.dump(event.to_dict(), f, ensure_ascii=False)
            f.write("\n")
    
    def get_events(self) -> List[MatrixEvent]:
        """Return in-memory copy of events."""
        return list(self._events)
    
    def __len__(self) -> int:
        return len(self._events)
