"""
Core Annotations Module
-----------------------
This module provides the data structures and repository for manual event annotations (ONY Studio).
Previously part of the 'sniper' module, these are now core primitives for the foundry pipeline.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
import json
import os

# --- Enums/Constants ---
class SniperStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVIEWED = "REVIEWED"

class SniperLabel:
    UNCERTAIN = "UNCERTAIN"
    GOOD = "GOOD"
    BAD = "BAD"

# --- ID Generation ---

def generate_rally_id(symbol: str, timeframe: str, event_time: Any, tier: str = "X") -> str:
    """
    Unified Event ID Generation.
    Format: {SYMBOL}_{TF}_{TIER_CODE}_{TIMESTAMP}
    e.g., BTCUSDT_15m_G_1741094100
    """
    import pandas as pd
    
    # 1. Normalize Timestamp
    if not isinstance(event_time, pd.Timestamp):
        ts_obj = pd.to_datetime(event_time)
    else:
        ts_obj = event_time
        
    if ts_obj.tz is not None:
        ts_obj = ts_obj.tz_localize(None)
        
    ts_unix = int(ts_obj.timestamp())
    
    # 2. Normalize Tier Code
    t = str(tier).upper()
    if "DIAMOND" in t: code = "D"
    elif "GOLD" in t: code = "G"
    elif "SILVER" in t: code = "S"
    elif "BRONZE" in t: code = "B"
    else: code = "X"
    
    return f"{symbol}_{timeframe}_{code}_{ts_unix}"

# --- Models ---

@dataclass
class SniperAnnotation:
    symbol: str
    timeframe: str
    event_id: str
    entry_bar_offset: int
    
    # Optional fields with defaults
    exit_bar_offset: Optional[int] = None
    note: str = ""
    status: str = SniperStatus.PENDING
    label: str = SniperLabel.UNCERTAIN
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    archetype: Optional[str] = None # For Kalıpçı labeling
    rev_gain: Optional[float] = None # Calculated gain for revised entry/exit window
    
    # Normalized Entry Fields (Auto-Snap)
    normalized_entry_bar_offset: Optional[int] = None
    normalized_entry_ts: Optional[str] = None
    snap_reason: Optional[str] = None
    snap_distance_bars: Optional[float] = None
    snap_confidence: Optional[float] = None
    snap_algo_version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SniperAnnotation':
        # Filter out unknown fields to be safe against schema drift
        known_fields = cls.__dataclass_fields__.keys()
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        return cls(**filtered_data)


# --- Repository ---

class SniperAnnotationRepository:
    """
    Repository for storing annotations.
    Storage path: .tezaver_matrix/foundry/annotations/{symbol}/{timeframe}.json
    """
    
    def __init__(self, root_dir: str = ".tezaver_matrix/foundry/annotations"):
        self.root_dir = Path(root_dir)

    def _file_path(self, symbol: str, timeframe: str) -> Path:
        return self.root_dir / symbol / f"{timeframe}.json"

    def _ensure_dir(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)

    def load_all(self, symbol: str, timeframe: str) -> List[SniperAnnotation]:
        """Load all annotations for a symbol/timeframe."""
        fpath = self._file_path(symbol, timeframe)
        if not fpath.exists():
            return []
        
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [SniperAnnotation.from_dict(item) for item in data]
        except Exception:
            return []

    def save_all(self, symbol: str, timeframe: str, annotations: List[SniperAnnotation]):
        """Save list of annotations."""
        fpath = self._file_path(symbol, timeframe)
        self._ensure_dir(fpath)
        
        data = [ann.to_dict() for ann in annotations]
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_one(self, symbol: str, timeframe: str, event_id: str) -> Optional[SniperAnnotation]:
        """Get a single annotation by event_id."""
        all_anns = self.load_all(symbol, timeframe)
        for ann in all_anns:
            if str(ann.event_id) == str(event_id):
                return ann
        return None

    def delete(self, symbol: str, timeframe: str, event_id: str) -> bool:
        """Delete an annotation by event_id."""
        all_anns = self.load_all(symbol, timeframe)
        initial_len = len(all_anns)
        all_anns = [a for a in all_anns if str(a.event_id) != str(event_id)]
        
        if len(all_anns) < initial_len:
            self.save_all(symbol, timeframe, all_anns)
            return True
        return False

    def append(self, 
               symbol: str, 
               timeframe: str, 
               event_id: str, 
               entry_bar_offset: int, 
               exit_bar_offset: Optional[int] = None,
               note: str = "",
               status: str = SniperStatus.PENDING,
               label: str = SniperLabel.UNCERTAIN,
               rev_gain: Optional[float] = None,
               **kwargs) -> SniperAnnotation:
        """
        Add or Update an annotation.
        If event_id exists, it updates it.
        """
        all_anns = self.load_all(symbol, timeframe)
        
        # Check if exists
        idx = -1
        existing = None
        for i, ann in enumerate(all_anns):
            if str(ann.event_id) == str(event_id):
                idx = i
                existing = ann
                break
        
        # Create new object
        new_ann = SniperAnnotation(
            symbol=symbol,
            timeframe=timeframe,
            event_id=str(event_id),
            entry_bar_offset=entry_bar_offset,
            exit_bar_offset=exit_bar_offset,
            note=note,
            status=status,
            label=label,
            rev_gain=rev_gain,
            # Preserve created_at if updating, else new
            created_at=existing.created_at if existing else datetime.now().isoformat()
        )
        
        # If existing had normalized fields, preserve them if not provided in kwargs?
        # The prompt implies simple replacement based on UI usage. 
        # But 'append' is used in UI with many args.
        # We will iterate kwargs for normalized fields if passed (from UI logic that might pass them later or manually set fields).
        # Actually in UI: "ann = repo.append(...)" creates/returns it, and then UI might set fields? 
        # No, the UI sets fields on the returned object, but doesn't persist them unless we save.
        # Wait, the UI code says:
        # ann = repo.append(...) -> This saves to disk immediately in my implementation.
        # If I want to persist normalized fields, I should handle them here or the UI needs to call save manually.
        # The UI code:
        #   ann = repo.append(...)
        #   st.success(...)
        # It assumes append saves it. 
        # But `apply_normalize_to_annotation` is called BEFORE `repo.append` in some blocks. 
        # Ah, in the "Apply" block: 
        #   ann = apply_normalize...(ann, ...)
        #   repo.append(..., entry_bar_offset=ann.entry_bar_offset...) 
        # The `repo.append` signature in UI call DOES NOT pass normalized fields.
        # So Normalized fields might be lost if I don't preserve them from `existing` record!
        
        if existing:
            # Preserve normalized fields from existing record
            new_ann.normalized_entry_bar_offset = existing.normalized_entry_bar_offset
            new_ann.normalized_entry_ts = existing.normalized_entry_ts
            new_ann.snap_reason = existing.snap_reason
            new_ann.snap_distance_bars = existing.snap_distance_bars
            new_ann.snap_confidence = existing.snap_confidence
            new_ann.snap_algo_version = existing.snap_algo_version
            if not new_ann.archetype: new_ann.archetype = existing.archetype # Preserve archetype if not overwritten

        # Allow kwargs to overwrite any field (e.g. archetype passed in kwargs)
        for k, v in kwargs.items():
            if hasattr(new_ann, k):
                setattr(new_ann, k, v)
            
        # Update list
        if idx >= 0:
            all_anns[idx] = new_ann
        else:
            all_anns.append(new_ann)
            
        self.save_all(symbol, timeframe, all_anns)
        return new_ann
