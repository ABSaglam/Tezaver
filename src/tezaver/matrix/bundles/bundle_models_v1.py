"""
ApprovedRallyBundle Models v1
==============================

Data models and validation for ApprovedRallyBundle v1 packages.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ApprovedRallyBundleManifestV1:
    """
    Validated manifest for ApprovedRallyBundle v1.
    
    Enforces required fields and QC validity.
    """
    # Required - Bundle metadata
    bundle_version: str
    bundle_id: str
    symbol: str
    timeframe: str
    event_id: str
    event_time_iso: str
    
    # Required - Approved values
    approved_entry_bar_offset: int
    approved_entry_ts: str
    
    # Required - QC metadata
    qc_verdict: str  # PASS|FAIL
    qc_score: int    # 0-100
    
    # Optional - Exit values
    approved_exit_bar_offset: Optional[int] = None
    approved_exit_ts: Optional[str] = None
    
    # Optional - Tier
    tier: Optional[str] = None
    
    # Optional - Pointers and trace
    pointers: Optional[Dict[str, str]] = None
    trace: Optional[Dict[str, str]] = None
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ApprovedRallyBundleManifestV1":
        """
        Load and validate manifest from dictionary.
        
        Args:
            data: Manifest data dictionary
        
        Returns:
            Validated manifest instance
        
        Raises:
            ValueError: If manifest is invalid
        """
        # Validate bundle_version
        bundle_version = data.get("bundle_version", "")
        if bundle_version != "approved_rally_bundle_v1":
            raise ValueError(f"MANIFEST_INVALID: bundle_version must be 'approved_rally_bundle_v1', got '{bundle_version}'")
        
        # Extract required fields
        required_fields = [
            "bundle_id", "symbol", "timeframe", "event_id", "event_time_iso"
        ]
        
        for field in required_fields:
            if field not in data:
                raise ValueError(f"MANIFEST_INVALID: missing required field '{field}'")
        
        # Extract approved values (required)
        approved = data.get("approved", {})
        if not approved:
            raise ValueError("MANIFEST_INVALID: missing 'approved' object")
        
        approved_entry_offset = approved.get("entry_bar_offset")
        approved_entry_ts = approved.get("entry_ts")
        
        if approved_entry_offset is None:
            raise ValueError("MANIFEST_INVALID: missing approved.entry_bar_offset")
        if not approved_entry_ts:
            raise ValueError("MANIFEST_INVALID: missing approved.entry_ts")
        
        # Extract QC (required)
        qc = data.get("qc", {})
        if not qc:
            raise ValueError("MANIFEST_INVALID: missing 'qc' object")
        
        qc_verdict = qc.get("verdict")
        qc_score = qc.get("score")
        
        if not qc_verdict:
            raise ValueError("MANIFEST_INVALID: missing qc.verdict")
        if qc_verdict not in ["PASS", "FAIL"]:
            raise ValueError(f"MANIFEST_INVALID: qc.verdict must be PASS or FAIL, got '{qc_verdict}'")
        
        if qc_score is None:
            raise ValueError("MANIFEST_INVALID: missing qc.score")
        if not isinstance(qc_score, int) or qc_score < 0 or qc_score > 100:
            raise ValueError(f"MANIFEST_INVALID: qc.score must be int 0-100, got {qc_score}")
        
        # Extract optional fields
        approved_exit_offset = approved.get("exit_bar_offset")
        approved_exit_ts = approved.get("exit_ts")
        tier = data.get("tier")
        pointers = data.get("pointers")
        trace = data.get("trace")
        
        return ApprovedRallyBundleManifestV1(
            bundle_version=bundle_version,
            bundle_id=data["bundle_id"],
            symbol=data["symbol"],
            timeframe=data["timeframe"],
            event_id=data["event_id"],
            event_time_iso=data["event_time_iso"],
            approved_entry_bar_offset=approved_entry_offset,
            approved_entry_ts=approved_entry_ts,
            qc_verdict=qc_verdict,
            qc_score=qc_score,
            approved_exit_bar_offset=approved_exit_offset,
            approved_exit_ts=approved_exit_ts,
            tier=tier,
            pointers=pointers,
            trace=trace
        )


@dataclass
class LoadedBundle:
    """
    Represents a loaded bundle with status.
    """
    manifest: ApprovedRallyBundleManifestV1
    bundle_dir: str
    status: str  # DISCOVERED | LOADED_OK | REJECTED
    reject_reason: Optional[str] = None
