"""
MX-26001: Tezaver Version Module

Provides version info and build metadata.
"""

import subprocess
from datetime import datetime

__version__ = "0.1.0"


def build_commit() -> str:
    """
    Get current git commit hash.
    TR: Git commit hash'ini döndürür.
    
    Returns "unknown" if not in a git repo.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return "unknown"


def build_time() -> str:
    """
    Get build timestamp.
    TR: Build zamanını ISO formatında döndürür.
    """
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def version_string() -> str:
    """
    Get full version string with commit.
    TR: Sürüm + commit bilgisini döndürür.
    """
    return f"Tezaver v{__version__} ({build_commit()})"
