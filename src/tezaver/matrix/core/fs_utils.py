"""
Tezaver Matrix - Filesystem Utilities (MX-9300)

Safe write utilities that ensure parent directories exist before writing.
"""
from pathlib import Path
from typing import Union


def ensure_dir(path: Union[str, Path]) -> Path:
    """
    Ensures a directory exists, creating it and all parents if necessary.
    Returns the Path object for chaining.
    """
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def ensure_parent(file_path: Union[str, Path]) -> Path:
    """
    Ensures the parent directory of a file exists.
    Returns the Path object for chaining.
    
    Usage:
        ensure_parent(report_path)
        with open(report_path, "w") as f:
            ...
    """
    p = Path(file_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
