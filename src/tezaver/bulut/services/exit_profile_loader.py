# Tezaver Bulut - Exit Profile Loader
"""
Loads and resolves exit profiles.
"""

import json
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.paths import get_data_dir
from tezaver.bulut.schemas.exit_profile_v1 import ExitProfileV1, DEFAULT_EXIT_PROFILE


class ExitProfileLoader:
    """
    Manages exit profiles from JSON files (hot-reloadable).
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
        self._profiles: Dict[str, ExitProfileV1] = {} # profile_id -> obj
        self._profiles_by_key: Dict[str, ExitProfileV1] = {} # sym+pat key -> obj
        self._last_reload_ts = 0
        self._profiles_dir = get_data_dir() / "bulut_rules" / "exit_profiles"
        self._profiles_dir.mkdir(parents=True, exist_ok=True)
        
    def check_reload(self):
        """Check for updates and reload if needed."""
        # Check dir mtime
        try:
            mtime = self._profiles_dir.stat().st_mtime
            if mtime > self._last_reload_ts:
                self._load_profiles()
                self._last_reload_ts = mtime
        except Exception as e:
            print(f"[EXIT_LOADER] Check failed: {e}")

    def _load_profiles(self):
        """Load all JSONs."""
        new_profiles = {}
        
        for p_file in self._profiles_dir.glob("*.json"):
            try:
                with open(p_file, "r") as f:
                    data = json.load(f)
                    
                profile = ExitProfileV1.from_dict(data)
                new_profiles[profile.profile_id] = profile
                
            except Exception as e:
                print(f"[EXIT_LOADER] Error loading {p_file}: {e}")
        
        self._profiles = new_profiles
        print(f"[EXIT_LOADER] Loaded {len(self._profiles)} profiles.")

    def resolve(self, symbol: str, pattern_id: Optional[str]) -> ExitProfileV1:
        """
        Resolve best profile.
        Priority:
        1. Symbol + Pattern Match
        2. Pattern Match (Symbol=null)
        3. Symbol Match (Pattern=null)
        4. Global (both null)
        5. Built-in Default
        """
        # Linear search through loaded profiles sort by priority descending
        # Pre-sorting candidates might be faster but N is small.
        
        candidates = list(self._profiles.values())
        candidates.sort(key=lambda p: p.priority, reverse=True)
        
        best = None
        
        for p in candidates:
            scope_sym = p.scope.symbol
            scope_pat = p.scope.pattern_id
            
            # Check Match
            sym_match = (scope_sym == symbol) or (scope_sym is None)
            pat_match = (scope_pat == pattern_id) or (scope_pat is None)
            
            if sym_match and pat_match:
                # Found a matching scope. Since we sorted by priority, first one is best?
                # Need to check specificity?
                # Usually priority handles specificity.
                # If priority equal, prefer more specific?
                # Simple logic for v0.08: Priority wins.
                best = p
                break
                
        return best or DEFAULT_EXIT_PROFILE
