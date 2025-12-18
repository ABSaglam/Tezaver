# Tezaver Bulut - Allowlist Source
"""
Loads allowlist for trading.
"""

from pathlib import Path
from typing import Optional, Set

from tezaver.bulut.core.config import BulutConfig


class AllowlistSource:
    """
    Source for allowed symbols.
    If file is missing, returns None (implying ALLOW_ALL).
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
    
    def load(self) -> Optional[Set[str]]:
        """
        Load allowed symbols.
        Returns:
            Set[str] of symbols if list exists.
            None if list should be ignored (ALLOW ALL).
        """
        path_str = self._config.allowlist_path
        if not path_str:
            return None # Allow all
            
        path = Path(path_str)
        if not path.exists():
            print(f"[ALLOWLIST] File not found: {path}. Defaulting to ALLOW_ALL.")
            return None
            
        allowed = set()
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    allowed.add(line)
            
            print(f"[ALLOWLIST] Loaded {len(allowed)} symbols.")
            return allowed
            
        except Exception as e:
            print(f"[ALLOWLIST] Error reading {path}: {e}")
            return None # Fail safe to allow all or block all? Usually allow all in this context or strict?
            # User requirement: "dosya yoksa empty set değil: “ALLOW_ALL” davranışı"
            # So let's stick to allowing all on error/missing to avoid blocking everything accidentally?
            # Or safer: if error reading existing file, maybe block?
            # For now, consistent with "missing" behavior -> None.
            return None
