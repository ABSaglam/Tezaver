"""
Bundle Registry
===============

In-memory registry for tracking loaded bundles.
"""

from typing import List, Dict, Optional
from tezaver.matrix.bundles.bundle_models_v1 import LoadedBundle


class BundleRegistry:
    """
    In-memory registry of loaded bundles.
    
    Tracks bundles by status: DISCOVERED, LOADED_OK, REJECTED.
    """
    
    def __init__(self):
        self._bundles: List[LoadedBundle] = []
    
    def add(self, bundle: LoadedBundle):
        """Add a bundle to the registry."""
        self._bundles.append(bundle)
    
    def list(self, status: Optional[str] = None) -> List[LoadedBundle]:
        """
        List bundles, optionally filtered by status.
        
        Args:
            status: Optional status filter
        
        Returns:
            List of bundles
        """
        if status:
            return [b for b in self._bundles if b.status == status]
        return self._bundles.copy()
    
    def counts(self) -> Dict[str, int]:
        """
        Get bundle counts by status.
        
        Returns:
            Dictionary with discovered/loaded_ok/rejected counts
        """
        discovered = sum(1 for b in self._bundles if b.status == "DISCOVERED")
        loaded_ok = sum(1 for b in self._bundles if b.status == "LOADED_OK")
        rejected = sum(1 for b in self._bundles if b.status == "REJECTED")
        
        return {
            "discovered": discovered,
            "loaded_ok": loaded_ok,
            "rejected": rejected,
            "total": len(self._bundles)
        }
    
    def clear(self):
        """Clear all bundles from registry."""
        self._bundles.clear()
