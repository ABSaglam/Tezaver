"""
Bundle Registry
===============

In-memory registry for tracking loaded bundles.
"""

from datetime import datetime, timezone
from typing import List, Dict, Optional
from tezaver.matrix.bundles.bundle_models_v1 import LoadedBundle


class BundleRegistry:
    """
    In-memory registry of loaded bundles.
    
    Tracks bundles by status: DISCOVERED, LOADED_OK, REJECTED.
    Supports reset for boot reconciliation.
    """
    
    def __init__(self):
        self._bundles: List[LoadedBundle] = []
        self._last_reconcile_ts: Optional[str] = None
        self._last_reconcile_counts: Optional[Dict[str, int]] = None
    
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

    def list_loaded_bundles(self) -> List[LoadedBundle]:
        """List all LOADED_OK bundles."""
        return self.list(status="LOADED_OK")

    def get(self, bundle_id: str) -> Optional[LoadedBundle]:
        """Get a bundle by ID (returns first match if duplicates exist)."""
        for b in self._bundles:
            if b.manifest and b.manifest.bundle_id == bundle_id:
                return b
        return None
    
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
    
    def reset(self):
        """
        Reset registry for boot reconciliation.
        
        Clears all bundles and prepares for fresh load.
        """
        self._bundles.clear()
    
    def mark_reconciled(self, counts: Dict[str, int]):
        """
        Mark registry as reconciled with given counts.
        
        Called after successful boot reconciliation.
        """
        self._last_reconcile_ts = datetime.now(timezone.utc).isoformat()
        self._last_reconcile_counts = counts.copy()
    
    @property
    def last_reconcile_ts(self) -> Optional[str]:
        """Get timestamp of last reconciliation."""
        return self._last_reconcile_ts
    
    @property
    def last_reconcile_counts(self) -> Optional[Dict[str, int]]:
        """Get counts from last reconciliation."""
        return self._last_reconcile_counts

