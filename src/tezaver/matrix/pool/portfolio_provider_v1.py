"""
Portfolio Provider V1
=====================

Interface and implementations for retrieving the current portfolio state.
Used by Pool Engine to calculate available capacity (Phase 2B).
"""
from typing import Protocol, List, Dict, Any

class PortfolioProviderV1(Protocol):
    """Protocol for portfolio providers."""
    def get_open_positions(self) -> List[Dict[str, Any]]:
        """Return list of open positions."""
        ...
        
    def get_source_name(self) -> str:
        """Return identifier of the data source."""
        ...

class StubPortfolioProviderV1:
    """Stub provider always returning empty or pre-configured positions."""
    
    def __init__(self, open_positions: List[Dict[str, Any]] = None):
        self._positions = open_positions or []
        
    def get_open_positions(self) -> List[Dict[str, Any]]:
        return self._positions
        
    def get_source_name(self) -> str:
        return "provider:stub"

class MatrixPortfolioProviderV1:
    """
    Real-world provider that connects to Matrix state.
    For Phase 2B, this is a placeholder that returns empty (safe fallback)
    since live state connection is not yet implemented.
    """
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        # TODO: Connect to live execution/position tracker (Phase 7+)
        # For now, safe default is empty (assumption: clean slate)
        return []
        
    def get_source_name(self) -> str:
        return "provider:matrix_fallback_empty"
