"""
Sniper Bundle Adapter v1
========================

Adapter for building SniperRunConfig from ApprovedRallyBundle v1 packages.
Enables Sniper runs to be started from Matrix-loaded bundles.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from tezaver.matrix.bundles.bundle_models_v1 import LoadedBundle


@dataclass
class SniperBundleRunConfig:
    """
    Configuration for Sniper run from bundle.
    
    Contains all necessary fields for running Sniper with approved bundle data.
    """
    # Core identifiers
    symbol: str
    timeframe: str
    bundle_id: str
    
    # Approved entry/exit
    entry_ts: str
    exit_ts: Optional[str]  # None = exit by policy mode
    
    # QC metadata
    qc_score: int
    tier: Optional[str]
    
    # Paths
    bundle_dir: str
    manifest_path: str
    price_window_path: Optional[str]  # Optional parquet
    
    # Flags
    exit_missing: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


def build_sniper_run_config_from_bundle(bundle: LoadedBundle) -> SniperBundleRunConfig:
    """
    Build SniperRunConfig from a LoadedBundle.
    
    Args:
        bundle: LoadedBundle instance from bundle loader
    
    Returns:
        SniperBundleRunConfig with all necessary fields
    
    Raises:
        ValueError: If bundle is not valid for Sniper run
            - BUNDLE_NOT_LOADED_OK: Bundle status is not LOADED_OK
            - BUNDLE_NOT_PASS: QC verdict is not PASS
            - APPROVED_ENTRY_MISSING: approved_entry_ts is missing
    
    Note:
        Missing exit_ts is allowed - Sniper can run in "exit by policy" mode.
    """
    # Validate bundle status
    if bundle.status != "LOADED_OK":
        raise ValueError(f"BUNDLE_NOT_LOADED_OK: Bundle status is '{bundle.status}', expected 'LOADED_OK'")
    
    # Validate manifest exists
    if bundle.manifest is None:
        raise ValueError("BUNDLE_NOT_LOADED_OK: Bundle has no manifest")
    
    manifest = bundle.manifest
    
    # Validate QC verdict
    if manifest.qc_verdict != "PASS":
        raise ValueError(f"BUNDLE_NOT_PASS: QC verdict is '{manifest.qc_verdict}', expected 'PASS'")
    
    # Validate approved entry
    if not manifest.approved_entry_ts:
        raise ValueError("APPROVED_ENTRY_MISSING: approved_entry_ts is required")
    
    # Check for exit (optional)
    exit_ts = manifest.approved_exit_ts
    exit_missing = exit_ts is None
    
    # Build paths
    bundle_dir = bundle.bundle_dir
    manifest_path = str(Path(bundle_dir) / "manifest.json")
    
    # Check for price_window.parquet
    price_window_path = None
    pw_path = Path(bundle_dir) / "price_window.parquet"
    if pw_path.exists():
        price_window_path = str(pw_path)
    
    return SniperBundleRunConfig(
        symbol=manifest.symbol,
        timeframe=manifest.timeframe,
        bundle_id=manifest.bundle_id,
        entry_ts=manifest.approved_entry_ts,
        exit_ts=exit_ts,
        qc_score=manifest.qc_score,
        tier=manifest.tier,
        bundle_dir=bundle_dir,
        manifest_path=manifest_path,
        price_window_path=price_window_path,
        exit_missing=exit_missing
    )


def emit_sniper_run_started(config: SniperBundleRunConfig, run_id: str) -> Dict[str, Any]:
    """
    Emit SNIPER_RUN_STARTED telemetry event with bundle info.
    
    Args:
        config: SniperBundleRunConfig from adapter
        run_id: Unique run identifier
    
    Returns:
        Telemetry event dictionary
    """
    event = {
        "event_type": "SNIPER_RUN_STARTED",
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "bundle_id": config.bundle_id,
        "symbol": config.symbol,
        "timeframe": config.timeframe,
        "entry_ts": config.entry_ts,
        "exit_ts": config.exit_ts,
        "qc_score": config.qc_score,
        "tier": config.tier,
        "bundle_dir": config.bundle_dir,
        "manifest_path": config.manifest_path,
        "exit_missing": config.exit_missing
    }
    
    print(f"[TELEMETRY] {json.dumps(event)}")
    return event


def emit_sniper_run_finished(
    config: SniperBundleRunConfig,
    run_id: str,
    result_summary: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Emit SNIPER_RUN_FINISHED telemetry event with bundle info.
    
    Args:
        config: SniperBundleRunConfig from adapter
        run_id: Unique run identifier
        result_summary: Optional result summary (cycles, pnl, etc.)
    
    Returns:
        Telemetry event dictionary
    """
    event = {
        "event_type": "SNIPER_RUN_FINISHED",
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "bundle_id": config.bundle_id,
        "symbol": config.symbol,
        "timeframe": config.timeframe,
        "qc_score": config.qc_score,
        "tier": config.tier,
        "exit_missing": config.exit_missing
    }
    
    # Add result summary if provided
    if result_summary:
        event["result"] = result_summary
    
    print(f"[TELEMETRY] {json.dumps(event)}")
    return event


def start_sniper_from_bundle(bundle: LoadedBundle, run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    High-level function to start Sniper run from a bundle.
    
    This is the main entry point for UI/API to trigger Sniper runs from bundles.
    
    Args:
        bundle: LoadedBundle instance
        run_id: Optional run ID (generated if not provided)
    
    Returns:
        Run result dictionary with:
        - run_id: str
        - config: SniperBundleRunConfig dict
        - status: str (STARTED | ERROR)
        - error: Optional[str]
        - telemetry: List of emitted events
    """
    from uuid import uuid4
    
    if not run_id:
        run_id = f"sniper_bundle_{uuid4().hex[:12]}"
    
    result = {
        "run_id": run_id,
        "config": None,
        "status": "ERROR",
        "error": None,
        "telemetry": []
    }
    
    try:
        # Build config
        config = build_sniper_run_config_from_bundle(bundle)
        result["config"] = config.to_dict()
        
        # Emit start event
        start_event = emit_sniper_run_started(config, run_id)
        result["telemetry"].append(start_event)
        
        # Note: Actual Sniper run execution would go here
        # For now, we just mark as started successfully
        result["status"] = "STARTED"
        
        # Emit finish event (placeholder - real implementation would call after run completes)
        # This is a simplified version for initial implementation
        
    except ValueError as e:
        result["error"] = str(e)
        result["status"] = "ERROR"
    
    return result
