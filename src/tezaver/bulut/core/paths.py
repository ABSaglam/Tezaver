# Tezaver Bulut - Path Utilities
"""
Centralized path management for Tezaver Bulut.
"""

from pathlib import Path
from typing import Optional


def get_project_root() -> Path:
    """Get project root directory."""
    # Assumes: src/tezaver/bulut/core/paths.py
    return Path(__file__).resolve().parent.parent.parent.parent.parent


def get_data_dir() -> Path:
    """Get data directory."""
    return get_project_root() / "data"


def get_pattern_pack_dir() -> Path:
    """Get pattern pack inbox directory."""
    from tezaver.bulut.core.config import get_config
    return Path(get_config().pattern_pack_dir)


def get_sqlite_path() -> Path:
    """Get SQLite database path."""
    from tezaver.bulut.core.config import get_config
    return Path(get_config().sqlite_path)


def get_ndjson_path() -> Path:
    """Get NDJSON telemetry path."""
    from tezaver.bulut.core.config import get_config
    return Path(get_config().ndjson_path)


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists, create if needed."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_parent_dir(path: Path) -> Path:
    """Ensure parent directory exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def list_pattern_packs() -> list[Path]:
    """List all pattern pack files in inbox."""
    pack_dir = get_pattern_pack_dir()
    if not pack_dir.exists():
        return []
    return sorted(pack_dir.glob("*.json"))


def get_latest_pattern_pack() -> Optional[Path]:
    """Get most recent pattern pack file."""
    packs = list_pattern_packs()
    return packs[-1] if packs else None
