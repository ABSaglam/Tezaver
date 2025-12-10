# Matrix V2 Live Config
"""
Configuration for live trading.
"""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MatrixLiveConfig:
    """
    Configuration for live trading mode.
    """
    enabled_profiles: list[str] = field(default_factory=list)
    initial_capital: float = 1000.0


def load_live_config(path: Path) -> MatrixLiveConfig:
    """
    Load live configuration from a JSON file.
    
    Args:
        path: Path to the config JSON file.
        
    Returns:
        Parsed MatrixLiveConfig.
        
    Raises:
        NotImplementedError: Implementation pending.
    """
    # Placeholder - implementation pending
    raise NotImplementedError("Live config loading not yet implemented")
