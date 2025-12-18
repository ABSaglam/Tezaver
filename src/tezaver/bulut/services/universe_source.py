# Tezaver Bulut - Universe Source Service
"""
Loads symbol universe from file or config fallback.
"""

from pathlib import Path
from typing import List, Optional
import os

from tezaver.bulut.core.config import BulutConfig


class UniverseSource:
    """
    Source for symbol universe.
    
    Priority:
    1. ENV UNIVERSE_PATH (handled via config)
    2. Config UNIVERSE_PATH (default to data/universe/universe_symbols.txt)
    3. Config UNIVERSE_FALLBACK_SYMBOLS
    
    File Format:
    - One symbol per line
    - # Comments supported
    - Empty lines ignored
    """
    
    def __init__(self, config: BulutConfig):
        self._config = config
    
    def load(self) -> List[str]:
        """Load universe symbols based on priority rules."""
        path_str = self._config.universe_path
        
        # 1. Try loading from file path (ENV or Config)
        if path_str:
            path = Path(path_str)
            if path.exists() and path.is_file():
                symbols = self._load_from_file(path)
                if symbols:
                    print(f"[UNIVERSE] Loaded {len(symbols)} symbols from {path}")
                    return symbols
                else:
                    print(f"[UNIVERSE] File {path} is empty or invalid.")
            else:
                # Only log simple not found if it's the default path
                if "data/universe/universe_symbols.txt" not in str(path):
                    print(f"[UNIVERSE] File not found: {path}")

        # 2. Fallback to hardcoded/config list
        fallback = self._config.universe_fallback_symbols
        if fallback:
            print(f"[UNIVERSE] Using fallback list ({len(fallback)} symbols)")
            return fallback
        
        # 3. Last resort - minimal list if config is totally empty to avoid crash
        print("[UNIVERSE] Warning: No universe source found. Returning empty list.")
        return []

    def _load_from_file(self, path: Path) -> List[str]:
        """Read symbols from file, ignoring comments and whitespace."""
        symbols = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines or comments
                    if not line or line.startswith("#"):
                        continue
                    symbols.append(line)
        except Exception as e:
            print(f"[UNIVERSE] Error reading {path}: {e}")
            return []
            
        return symbols
