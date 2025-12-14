# Matrix Live Secrets Vault
"""
Secrets management for live trading.

IMPORTANT: API keys/secrets should NEVER be stored in:
- Code files
- data/ directory
- Git-tracked files

Supported sources:
- Environment variables (recommended)
- Local file (must be in .gitignore)
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional, Dict, List


class ISecretsVault(ABC):
    """Interface for secrets retrieval."""
    
    @abstractmethod
    def get(self, name: str) -> Optional[str]:
        """Get secret value by name. Returns None if not found."""
        ...
    
    def has(self, name: str) -> bool:
        """Check if secret exists."""
        return self.get(name) is not None
    
    def get_status(self, name: str) -> str:
        """Get status string for UI display."""
        return "FOUND" if self.has(name) else "MISSING"


class EnvSecretsVault(ISecretsVault):
    """
    Secrets from environment variables.
    
    Recommended for production. Set via:
    - Shell export
    - .env file (loaded externally)
    - CI/CD secrets
    """
    
    def __init__(self, prefix: str = "TEZAVER_"):
        self._prefix = prefix
    
    def get(self, name: str) -> Optional[str]:
        """Get secret from environment with optional prefix."""
        # Try with prefix first
        value = os.environ.get(f"{self._prefix}{name}")
        if value:
            return value
        # Fallback to raw name
        return os.environ.get(name)


class FileSecretsVault(ISecretsVault):
    """
    Secrets from local file.
    
    For local development only.
    File format: KEY=VALUE (one per line)
    
    WARNING: Add this file to .gitignore!
    """
    
    def __init__(self, path: Path | str):
        self._path = Path(path)
        self._cache: Dict[str, str] = {}
        self._load()
    
    def _load(self) -> None:
        """Load secrets from file."""
        if not self._path.exists():
            return
        
        for line in self._path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                self._cache[key.strip()] = value.strip()
    
    def get(self, name: str) -> Optional[str]:
        return self._cache.get(name)


class CompositeVault(ISecretsVault):
    """
    Composite vault that tries multiple sources.
    
    Order matters: first vault with a value wins.
    """
    
    def __init__(self, vaults: List[ISecretsVault]):
        self._vaults = vaults
    
    def get(self, name: str) -> Optional[str]:
        for vault in self._vaults:
            value = vault.get(name)
            if value:
                return value
        return None


# =============================================================================
# Redaction Utilities
# =============================================================================

SENSITIVE_KEYS = frozenset([
    "api_key", "api_secret", "secret", "password", "token",
    "Authorization", "signature", "private_key", "apikey",
    "apiSecret", "API_KEY", "API_SECRET",
])


def redact_secrets(data: Dict) -> Dict:
    """
    Redact sensitive values from a dictionary.
    
    Use before logging telemetry events.
    """
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = redact_secrets(value)
        elif key.lower() in {k.lower() for k in SENSITIVE_KEYS}:
            result[key] = "***REDACTED***"
        else:
            result[key] = value
    
    return result


# =============================================================================
# Default Vault Factory
# =============================================================================

def create_default_vault() -> ISecretsVault:
    """
    Create default secrets vault.
    
    Order: Environment -> Local file (if exists)
    """
    vaults = [EnvSecretsVault()]
    
    # Check for local secrets file (never in data/)
    local_path = Path.home() / ".tezaver_secrets"
    if local_path.exists():
        vaults.append(FileSecretsVault(local_path))
    
    return CompositeVault(vaults)


def check_file_permissions(path: Path | str) -> Dict:
    """
    Check file permissions for secrets file.
    
    Returns dict with:
    - exists: bool
    - mode: octal string (e.g., "600")
    - is_secure: bool (True if mode is 600 or more restrictive)
    - warning: optional warning message
    """
    path = Path(path)
    
    if not path.exists():
        return {
            "exists": False,
            "mode": None,
            "is_secure": False,
            "warning": f"File not found: {path}",
        }
    
    try:
        stat_info = path.stat()
        mode_octal = oct(stat_info.st_mode)[-3:]
        
        # Check if permissions are 600 or more restrictive
        is_secure = mode_octal in ("600", "400", "000")
        
        warning = None
        if not is_secure:
            warning = f"File permissions are {mode_octal}. Should be 600 for security."
        
        return {
            "exists": True,
            "mode": mode_octal,
            "is_secure": is_secure,
            "warning": warning,
        }
    except Exception as e:
        return {
            "exists": True,
            "mode": "???",
            "is_secure": False,
            "warning": f"Could not check permissions: {e}",
        }


def get_vault_status(source: str = "ENV", file_path: str = "") -> Dict:
    """
    Get secrets vault status for UI display.
    
    Args:
        source: "ENV" or "FILE"
        file_path: path to secrets file (only used if source is FILE)
    
    Returns dict with:
        source, api_key_status, api_secret_status, file_permissions, warnings
    """
    warnings = []
    
    if source == "ENV":
        vault = EnvSecretsVault()
        file_perms = None
    else:
        if file_path:
            path = Path(file_path)
            file_perms = check_file_permissions(path)
            if file_perms.get("warning"):
                warnings.append(file_perms["warning"])
            if path.exists():
                vault = FileSecretsVault(path)
            else:
                vault = EnvSecretsVault()  # Fallback
                warnings.append(f"File not found: {file_path}")
        else:
            vault = EnvSecretsVault()  # Fallback
            file_perms = None
            warnings.append("No file path specified")
    
    api_key_status = vault.get_status("BINANCE_API_KEY")
    api_secret_status = vault.get_status("BINANCE_API_SECRET")
    
    # Also check alternate key names
    if api_key_status == "MISSING":
        api_key_status = vault.get_status("API_KEY")
    if api_secret_status == "MISSING":
        api_secret_status = vault.get_status("API_SECRET")
    
    return {
        "source": source,
        "api_key_status": api_key_status,
        "api_secret_status": api_secret_status,
        "file_permissions": file_perms,
        "warnings": warnings,
        "all_present": api_key_status == "FOUND" and api_secret_status == "FOUND",
    }

