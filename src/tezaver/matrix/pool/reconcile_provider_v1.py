"""
Reconcile Provider V1
=====================

Interface and implementations for retrieving position snapshots for reconciliation.
"""
from typing import Protocol, List, Dict, Any

class OpenPositionsProviderV1(Protocol):
    """Protocol for position snapshot providers."""
    def snapshot(self) -> Dict[str, Any]:
        """
        Return snapshot of open positions.
        
        Returns:
            {"positions": [...], "count": int, "source": str}
        """
        ...

class StubOpenPositionsProviderV1:
    """Stub provider for testing - returns empty or pre-configured positions."""
    
    def __init__(self, positions: List[Dict[str, Any]] = None):
        self._positions = positions or []
        
    def snapshot(self) -> Dict[str, Any]:
        return {
            "positions": self._positions,
            "count": len(self._positions),
            "source": "stub"
        }

class MatrixOpenPositionsProviderV1:
    """
    Real-world provider that connects to Matrix state.
    For Phase 2D, this is a placeholder that returns empty (safe fallback).
    """
    
    def snapshot(self) -> Dict[str, Any]:
        # TODO: Connect to live position tracker / state (Phase 7+)
        return {
            "positions": [],
            "count": 0,
            "source": "matrix_fallback_empty"
        }
