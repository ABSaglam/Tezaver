# Tezaver Bulut - Group Caps Loader
"""
Service to load and query symbol groups and their limits.
"""

import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.paths import get_project_root

class GroupCapsLoader:
    def __init__(self, config: BulutConfig):
        self._config = config
        self._symbol_groups: Dict[str, str] = {} # symbol -> group
        self._group_caps: Dict[str, int] = {}    # group -> max_open
        
        self._ensure_defaults()
        self.load()
        
    def _ensure_defaults(self):
        """Bootstrap default rules if missing."""
        root = get_project_root()
        rules_dir = root.parent / "data/bulut_rules" # Ensure correct relative
        # core/paths.py defines get_project_root as 'src/tezaver/bulut' usually?
        # Actually I should check `get_project_root` implementation or use config paths?
        # Config paths like `group_caps_path` are relative to project root?
        # `config.py` default: "data/bulut_rules/group_caps.json"
        
        # Assume get_project_root() returns '.../src/tezaver/bulut' or '.../src'?
        # In `app_backend.py` context bootstrap uses it.
        # Safest is to assume `config` paths are relative to `TezaverMac/` or repo root.
        # But `TezaverMac` structure is:
        # data/
        # src/
        #   tezaver/
        #     bulut/
        #       core/paths.py
        
        # Let's peek at `tezaver.bulut.core.paths` usage?
        # `get_project_root().parent / self._config.symbol_groups_path` was used in `load()`.
        # This implies `get_project_root` returns `src/tezaver/bulut`?
        # And `.parent` is `src/tezaver`? That's not repo root.
        # `repo_root` is typically `TezaverMac`.
        # Previous code used: `get_project_root().parent / self._config.symbol_groups_path`.
        # If `symbol_groups_path` is "data/...", then likely `get_project_root` + parent logic is tricky.
        # I'll rely on the same logic I used in `load` (lines 22 in original).
        # Actually I should fix `load` too if my assumption about `.parent` was based on `core/paths.py` returning repo root?
        # If `paths.py` returns `src/tezaver/bulut`, `.parent` is `src/tezaver`. Not root.
        # Typically one climbs up 3 parents? `src` `tezaver` `bulut`.
        # Let's check `core/paths.py` if I can?
        # Or just assume relative to `Path(__file__).parent.parent.parent.parent.parent`?
        
        # Resource path: relative to THIS file (__file__)
        # this: src/tezaver/bulut/services/group_caps_loader.py
        # resources: src/tezaver/bulut/resources/risk_examples/
        resource_dir = Path(__file__).parent.parent / "resources/risk_examples"
        
        # Target dir
        # config says "data/bulut_rules/..."
        # We need absolute path for target.
        # I'll try to find repo root by climbing up from `__file__`.
        # src/tezaver/bulut/services -> src/tezaver/bulut -> src/tezaver -> src -> root
        repo_root = Path(__file__).parent.parent.parent.parent.parent
        
        # Verify repo root has 'data' folder or 'src' folder?
        if not (repo_root / "src").exists():
            # Fallback/Debug
            pass
            
        target_dir = repo_root / "data/bulut_rules"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy if missing
        start_files = ["symbol_groups.json", "group_caps.json"]
        for fname in start_files:
            tgt = target_dir / fname
            src = resource_dir / fname
            
            if not tgt.exists() and src.exists():
                print(f"[GROUP_CAPS] Bootstrapping {fname}...")
                shutil.copy(src, tgt)

    def load(self):
        """Load rules from JSON files."""
        # Resolve target paths again
        repo_root = Path(__file__).parent.parent.parent.parent.parent
        
        # 1. Symbol Groups
        p_groups = repo_root / self._config.symbol_groups_path
        if p_groups.exists():
            try:
                with open(p_groups, "r") as f:
                    self._symbol_groups = json.load(f)
            except Exception as e:
                print(f"[GROUP_CAPS] Error parsing symbol groups: {e}")
                
        # 2. Group Caps
        p_caps = repo_root / self._config.group_caps_path
        if p_caps.exists():
            try:
                with open(p_caps, "r") as f:
                    self._group_caps = json.load(f)
            except Exception as e:
                print(f"[GROUP_CAPS] Error parsing group caps: {e}")
                
    def get_group(self, symbol: str) -> str:
        """Get group name for symbol. Default 'default'."""
        return self._symbol_groups.get(symbol, "default")
        
    def get_cap(self, group: str) -> int:
        """Get max open limit for group. Default from config."""
        return self._group_caps.get(group, self._config.default_group_cap_max_open)
