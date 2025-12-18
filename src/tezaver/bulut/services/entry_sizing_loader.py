# Tezaver Bulut - Entry Sizing Loader
"""
Loads Entry Sizing Profiles from disk.
Supports hot-reload indexing.
"""

import json
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from tezaver.bulut.schemas.entry_sizing_profile_v1 import EntrySizingProfileV1

class EntrySizingLoader:
    def __init__(self, rules_dir: Path):
        self._profiles_dir = rules_dir / "entry_sizing_profiles"
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        self._cache: List[EntrySizingProfileV1] = []
        self._last_scan: float = 0.0
        self._scan_interval: float = 5.0 # seconds
        self._indexed_map: Dict[str, List[EntrySizingProfileV1]] = {} # scope_key -> profiles override

    def load_all(self, force: bool = False) -> List[EntrySizingProfileV1]:
        """Load and return all valid profiles. Checks mtime if not forced."""
        now = datetime.now().timestamp()
        if not force and (now - self._last_scan < self._scan_interval):
             return self._cache
             
        self._load_from_disk()
        self._last_scan = now
        return self._cache

    def _load_from_disk(self):
        loaded = []
        if not self._profiles_dir.exists():
            self._cache = []
            return

        for p in self._profiles_dir.glob("*.json"):
            try:
                with open(p, "r") as f:
                    data = json.load(f)
                
                profile = EntrySizingProfileV1.from_dict(data)
                if profile:
                    loaded.append(profile)
            except Exception as e:
                print(f"[SIZING_LOADER] Error loading {p.name}: {e}")
        
        # Sort globally by priority desc for default listing
        loaded.sort(key=lambda x: x.priority, reverse=True)
        self._cache = loaded
        self._build_index(loaded)
        
    def _build_index(self, profiles: List[EntrySizingProfileV1]):
        """
        Builds lookup index.
        """
        # We can index by "symbol+pattern", "symbol", "pattern", "global"
        # Since resolution logic iterates through precedence, we rely on resolver to filter.
        # But we could pre-bucket them.
        pass

    def get_by_id(self, profile_id: str) -> Optional[EntrySizingProfileV1]:
        self.load_all() # ensure fresh
        for p in self._cache:
            if p.profile_id == profile_id:
                return p
        return None
