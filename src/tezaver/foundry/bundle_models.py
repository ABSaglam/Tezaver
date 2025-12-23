"""
Bundle Data Models
==================

Data structures for ApprovedRallyBundle packaging.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional
from datetime import datetime


@dataclass
class ApprovedRallyBundleManifest:
    """
    Manifest for ApprovedRallyBundle v1.
    
    Represents a QC-PASSED, approved rally event packaged for Matrix consumption.
    """
    bundle_version: str = "approved_rally_bundle_v1"
    bundle_id: str = ""  # {symbol}_{tf}_{event_id}
    
    # Event identifiers
    symbol: str = ""
    timeframe: str = ""
    event_id: str = ""
    event_time_iso: str = ""
    
    # Rally tier (from future_max_gain_pct)
    tier: str = "UNKNOWN"  # DIAMOND|GOLD|SILVER|BRONZE|UNKNOWN
    
    # Approved values (final truth for Matrix)
    approved: Dict[str, Any] = field(default_factory=dict)
    # Expected keys:
    #   entry_bar_offset, entry_ts
    #   exit_bar_offset, exit_ts (optional)
    
    # QC metadata
    qc: Dict[str, Any] = field(default_factory=dict)
    # Expected keys:
    #   verdict, score, report_path
    
    # File pointers (relative paths from bundle dir)
    pointers: Dict[str, str] = field(default_factory=dict)
    # Expected keys:
    #   annotation_path, event_dataset_path, history_path
    
    # Build trace
    trace: Optional[Dict[str, str]] = None
    build_ts_iso: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ApprovedRallyBundleManifest":
        """Load from dictionary."""
        return ApprovedRallyBundleManifest(
            bundle_version=data.get("bundle_version", "approved_rally_bundle_v1"),
            bundle_id=data.get("bundle_id", ""),
            symbol=data.get("symbol", ""),
            timeframe=data.get("timeframe", ""),
            event_id=data.get("event_id", ""),
            event_time_iso=data.get("event_time_iso", ""),
            tier=data.get("tier", "UNKNOWN"),
            approved=data.get("approved", {}),
            qc=data.get("qc", {}),
            pointers=data.get("pointers", {}),
            trace=data.get("trace"),
            build_ts_iso=data.get("build_ts_iso", "")
        )
