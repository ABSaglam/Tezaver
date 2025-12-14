"""
Sniper Lab Annotations - Data model for manual sniper entry marking.

This module provides storage and retrieval for sniper entry annotations
on rally patterns. V2 includes status/label workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
import json
import datetime

# Type aliases for V2 workflow
SniperStatus = Literal["PENDING", "REVIEWED", "APPROVED", "REJECTED"]
SniperLabel = Literal["GOOD", "BAD", "UNCERTAIN"]


@dataclass
class SniperAnnotation:
    """A single sniper entry annotation for a rally pattern."""
    symbol: str
    timeframe: str
    event_id: str          # rally / pattern ID
    entry_bar_offset: int  # rally penceresi içindeki bar offset'i (0 = ilk bar)
    note: str = ""
    created_at: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    
    # Optional fields
    exit_bar_offset: Optional[int] = None
    tags: Optional[List[str]] = None
    
    # V2 Workflow fields
    status: SniperStatus = "PENDING"
    label: SniperLabel = "UNCERTAIN"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "SniperAnnotation":
        """Parse from dict with backward compatibility."""
        return SniperAnnotation(
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            event_id=str(data["event_id"]),
            entry_bar_offset=int(data["entry_bar_offset"]),
            note=data.get("note", ""),
            created_at=data.get("created_at", ""),
            exit_bar_offset=data.get("exit_bar_offset"),
            tags=data.get("tags"),
            # V2 fields with backward compatibility defaults
            status=data.get("status", "PENDING"),
            label=data.get("label", "UNCERTAIN"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SniperAnnotationRepository:
    """
    Coin/timeframe bazlı sniper annotation depolama.
    
    Storage path: data/sniper/{symbol}/{timeframe}/sniper_annotations_v1.json
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        if base_dir is None:
            base_dir = Path("data/sniper")
        self.base_dir = base_dir

    def _file_path(self, symbol: str, timeframe: str) -> Path:
        return (
            self.base_dir
            / symbol.upper()
            / timeframe
            / "sniper_annotations_v1.json"
        )

    def load_all(self, symbol: str, timeframe: str) -> List[SniperAnnotation]:
        """Load all annotations for a symbol/timeframe."""
        path = self._file_path(symbol, timeframe)
        if not path.exists():
            return []
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return [SniperAnnotation.from_dict(item) for item in raw]

    def save_all(
        self,
        symbol: str,
        timeframe: str,
        annotations: List[SniperAnnotation],
    ) -> None:
        """Save all annotations for a symbol/timeframe."""
        path = self._file_path(symbol, timeframe)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [a.to_dict() for a in annotations]
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    # ========== V2 Helper Methods ==========

    def list_by_status(
        self, symbol: str, timeframe: str, status: SniperStatus
    ) -> List[SniperAnnotation]:
        """Filter annotations by status."""
        all_anns = self.load_all(symbol, timeframe)
        return [a for a in all_anns if a.status == status]

    def get_next_pending(
        self, symbol: str, timeframe: str, current_event_id: Optional[str] = None
    ) -> Optional[SniperAnnotation]:
        """
        Get next PENDING annotation after current_event_id.
        If current_event_id is None, returns the first PENDING.
        """
        pending = self.list_by_status(symbol, timeframe, "PENDING")
        if not pending:
            return None
        
        if current_event_id is None:
            return pending[0]
        
        # Find index of current and return next
        for i, ann in enumerate(pending):
            if str(ann.event_id) == str(current_event_id):
                if i + 1 < len(pending):
                    return pending[i + 1]
                else:
                    return pending[0]  # Wrap around
        
        # Current not found, return first
        return pending[0]

    def upsert_annotation(self, annotation: SniperAnnotation) -> SniperAnnotation:
        """
        Insert or update annotation.
        If annotation with same (symbol, timeframe, event_id) exists, update it.
        """
        annotations = self.load_all(annotation.symbol, annotation.timeframe)
        
        # Remove existing if any
        annotations = [
            a for a in annotations 
            if str(a.event_id) != str(annotation.event_id)
        ]
        
        # Update created_at if not set
        if not annotation.created_at:
            annotation.created_at = datetime.datetime.utcnow().isoformat()
        
        annotations.append(annotation)
        self.save_all(annotation.symbol, annotation.timeframe, annotations)
        return annotation

    def append(
        self,
        symbol: str,
        timeframe: str,
        event_id: str,
        entry_bar_offset: int,
        note: str = "",
        exit_bar_offset: Optional[int] = None,
        tags: Optional[List[str]] = None,
        status: SniperStatus = "PENDING",
        label: SniperLabel = "UNCERTAIN",
    ) -> SniperAnnotation:
        """Append/upsert a new annotation and save."""
        ann = SniperAnnotation(
            symbol=symbol.upper(),
            timeframe=timeframe,
            event_id=str(event_id),
            entry_bar_offset=int(entry_bar_offset),
            note=note,
            exit_bar_offset=exit_bar_offset,
            tags=tags or [],
            status=status,
            label=label,
        )
        return self.upsert_annotation(ann)

    def by_event_id(
        self, symbol: str, timeframe: str, event_id: str
    ) -> List[SniperAnnotation]:
        """Get all annotations for a specific event."""
        all_anns = self.load_all(symbol, timeframe)
        return [a for a in all_anns if str(a.event_id) == str(event_id)]

    def get_one(
        self, symbol: str, timeframe: str, event_id: str
    ) -> Optional[SniperAnnotation]:
        """Get single annotation for event_id (returns first match or None)."""
        matches = self.by_event_id(symbol, timeframe, event_id)
        return matches[0] if matches else None

    def delete_by_event_id(
        self, symbol: str, timeframe: str, event_id: str
    ) -> int:
        """Delete all annotations for a specific event. Returns count deleted."""
        anns = self.load_all(symbol, timeframe)
        original_count = len(anns)
        filtered = [a for a in anns if str(a.event_id) != str(event_id)]
        self.save_all(symbol, timeframe, filtered)
        return original_count - len(filtered)
