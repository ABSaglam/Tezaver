# Tezaver Bulut - Group Caps Loader
"""
Service to load and query symbol groups and their limits.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List

from tezaver.bulut.core.config import BulutConfig

class GroupCapsLoader:
    def __init__(self, config: BulutConfig):
        self._config = config
        self._symbol_groups: Dict[str, str] = {} # symbol -> group
        self._group_caps: Dict[str, int] = {}    # group -> max_open
        self._last_mtime: float = 0
        
        self.load()
        
    def load(self):
        """Load rules from JSON files."""
        repo_root = Path(__file__).parent.parent.parent.parent.parent
        
        p_groups = repo_root / self._config.symbol_groups_path
        p_caps = repo_root / self._config.group_caps_path
        
        self._symbol_groups = self._load_symbol_groups(p_groups)
        self._group_caps = self._load_group_caps(p_caps)
        
    def _load_symbol_groups(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                data = json.load(f)
                # Validation: keys are strings, values are strings
                return {str(k): str(v) for k, v in data.items()}
        except Exception as e:
            print(f"[GROUP_CAPS] Error loading groups: {e}")
            return {}

    def _load_group_caps(self, path: Path) -> Dict[str, int]:
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                data = json.load(f)
                valid = {}
                for k, v in data.items():
                    try:
                        cap = int(v)
                        if cap >= 0:
                            valid[k] = cap
                    except: pass
                return valid
        except Exception as e:
            print(f"[GROUP_CAPS] Error loading caps: {e}")
            return {}

    def reload_if_changed(self):
        """Reload if files changed (simple implementation: just reload)."""
        # For efficiency, we could check mtime.
        # For logic implementation:
        self.load()
        
    def get_group(self, symbol: str) -> str:
        """Get group name for symbol. Default 'default'."""
        return self._symbol_groups.get(symbol, "default")
        
    def get_cap(self, group: str) -> int:
        """Get max open limit for group. Default from config."""
        return self._group_caps.get(group, self._config.default_group_cap_max_open)
    
    def get_open_counts(self, open_positions: List[Dict]) -> Dict[str, int]:
        """Calculate open positions per group."""
        counts = {}
        for p in open_positions:
            sym = p["symbol"]
            grp = self.get_group(sym)
            counts[grp] = counts.get(grp, 0) + 1
        return counts
                
    def get_group(self, symbol: str) -> str:
        """Get group name for symbol. Default 'default'."""
        return self._symbol_groups.get(symbol, "default")
        
    def get_cap(self, group: str) -> int:
        """Get max open limit for group. Default from config."""
        return self._group_caps.get(group, self._config.default_group_cap_max_open)
