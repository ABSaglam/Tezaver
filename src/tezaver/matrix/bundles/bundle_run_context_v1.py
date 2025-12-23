"""
Bundle Run Context v1
=====================

Common context dataclass for running Sniper/WAR/LIVE from ApprovedRallyBundle v1.
Provides unified interface for bundle-based run configuration across all modes.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

from tezaver.matrix.bundles.bundle_models_v1 import LoadedBundle


@dataclass
class BundleRunContextV1:
    """
    Common context for bundle-based runs across Sniper/WAR/LIVE.
    
    Provides unified configuration extracted from ApprovedRallyBundle v1.
    """
    # Core identifiers
    bundle_id: str
    symbol: str
    timeframe: str
    
    # QC metadata
    qc_score: int
    tier: Optional[str]
    
    # Paths
    bundle_dir: str
    manifest_path: str
    price_window_path: Optional[str]
    
    # Approved entry/exit
    entry_ts: str
    exit_ts: Optional[str]
    exit_missing: bool
    
    # Trace pointers
    event_id: Optional[str] = None
    trace: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)


def build_context_from_loaded_bundle(bundle: LoadedBundle) -> BundleRunContextV1:
    """
    Build BundleRunContextV1 from a LoadedBundle.
    
    Args:
        bundle: LoadedBundle instance from bundle loader
    
    Returns:
        BundleRunContextV1 with all necessary fields
    
    Raises:
        ValueError: If bundle is not valid for run
            - BUNDLE_NOT_LOADED_OK: Bundle status is not LOADED_OK
            - BUNDLE_NOT_PASS: QC verdict is not PASS
            - APPROVED_ENTRY_MISSING: approved_entry_ts is missing
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
    
    return BundleRunContextV1(
        bundle_id=manifest.bundle_id,
        symbol=manifest.symbol,
        timeframe=manifest.timeframe,
        qc_score=manifest.qc_score,
        tier=manifest.tier,
        bundle_dir=bundle_dir,
        manifest_path=manifest_path,
        price_window_path=price_window_path,
        entry_ts=manifest.approved_entry_ts,
        exit_ts=exit_ts,
        exit_missing=exit_missing,
        event_id=manifest.event_id,
        trace=manifest.trace
    )


# =============================================================================
# WAR Bundle Consume
# =============================================================================

def emit_war_run_started(ctx: BundleRunContextV1, run_id: str) -> Dict[str, Any]:
    """
    Emit WAR_RUN_STARTED telemetry event with bundle info.
    
    Args:
        ctx: BundleRunContextV1 from adapter
        run_id: Unique run identifier
    
    Returns:
        Telemetry event dictionary
    """
    event = {
        "event_type": "WAR_RUN_STARTED",
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "bundle_id": ctx.bundle_id,
        "symbol": ctx.symbol,
        "timeframe": ctx.timeframe,
        "entry_ts": ctx.entry_ts,
        "exit_ts": ctx.exit_ts,
        "qc_score": ctx.qc_score,
        "tier": ctx.tier,
        "bundle_dir": ctx.bundle_dir,
        "exit_missing": ctx.exit_missing
    }
    
    print(f"[TELEMETRY] {json.dumps(event)}")
    return event


def emit_war_run_finished(
    ctx: BundleRunContextV1,
    run_id: str,
    result_summary: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Emit WAR_RUN_FINISHED telemetry event with bundle info.
    
    Args:
        ctx: BundleRunContextV1 from adapter
        run_id: Unique run identifier
        result_summary: Optional result summary
    
    Returns:
        Telemetry event dictionary
    """
    event = {
        "event_type": "WAR_RUN_FINISHED",
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "bundle_id": ctx.bundle_id,
        "symbol": ctx.symbol,
        "timeframe": ctx.timeframe,
        "qc_score": ctx.qc_score,
        "tier": ctx.tier,
        "exit_missing": ctx.exit_missing
    }
    
    if result_summary:
        event["result"] = result_summary
    
    print(f"[TELEMETRY] {json.dumps(event)}")
    return event


def start_war_from_bundle(bundle: LoadedBundle, run_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Start WAR run from a bundle.
    
    Args:
        bundle: LoadedBundle instance
        run_id: Optional run ID (generated if not provided)
    
    Returns:
        Run result dictionary with:
        - run_id: str
        - context: BundleRunContextV1 dict
        - status: str (STARTED | ERROR)
        - error: Optional[str]
        - telemetry: List of emitted events
    """
    from uuid import uuid4
    
    if not run_id:
        run_id = f"war_bundle_{uuid4().hex[:12]}"
    
    result = {
        "run_id": run_id,
        "context": None,
        "status": "ERROR",
        "error": None,
        "telemetry": []
    }
    
    try:
        # Build context
        ctx = build_context_from_loaded_bundle(bundle)
        result["context"] = ctx.to_dict()
        
        # Emit start event
        start_event = emit_war_run_started(ctx, run_id)
        result["telemetry"].append(start_event)
        
        # Note: Actual WAR run execution would go here
        # For now, this is a minimal dry-run
        result["status"] = "STARTED"
        
    except ValueError as e:
        result["error"] = str(e)
        result["status"] = "ERROR"
    
    return result


# =============================================================================
# LIVE Bundle Arm
# =============================================================================

def emit_live_bundle_armed(ctx: BundleRunContextV1, arm_id: str) -> Dict[str, Any]:
    """
    Emit LIVE_BUNDLE_ARMED telemetry event with bundle info.
    
    This event indicates a bundle has been armed for LIVE trading.
    No orders are sent - this is configuration/trace only.
    
    Args:
        ctx: BundleRunContextV1 from adapter
        arm_id: Unique arm identifier
    
    Returns:
        Telemetry event dictionary
    """
    event = {
        "event_type": "LIVE_BUNDLE_ARMED",
        "ts": datetime.now(timezone.utc).isoformat(),
        "arm_id": arm_id,
        "bundle_id": ctx.bundle_id,
        "symbol": ctx.symbol,
        "timeframe": ctx.timeframe,
        "entry_ts": ctx.entry_ts,
        "exit_ts": ctx.exit_ts,
        "qc_score": ctx.qc_score,
        "tier": ctx.tier,
        "bundle_dir": ctx.bundle_dir,
        "exit_missing": ctx.exit_missing
    }
    
    print(f"[TELEMETRY] {json.dumps(event)}")
    return event


def arm_live_from_bundle(bundle: LoadedBundle, arm_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Arm LIVE trading from a bundle (no orders sent - config/trace only).
    
    Args:
        bundle: LoadedBundle instance
        arm_id: Optional arm ID (generated if not provided)
    
    Returns:
        Arm result dictionary with:
        - arm_id: str
        - context: BundleRunContextV1 dict
        - status: str (ARMED | ERROR)
        - error: Optional[str]
        - telemetry: List of emitted events
    """
    from uuid import uuid4
    
    if not arm_id:
        arm_id = f"live_arm_{uuid4().hex[:12]}"
    
    result = {
        "arm_id": arm_id,
        "context": None,
        "status": "ERROR",
        "error": None,
        "telemetry": []
    }
    
    try:
        # Build context
        ctx = build_context_from_loaded_bundle(bundle)
        result["context"] = ctx.to_dict()
        
        # Emit armed event
        armed_event = emit_live_bundle_armed(ctx, arm_id)
        result["telemetry"].append(armed_event)
        
        # Note: No actual trading logic here
        # This is configuration/trace only
        result["status"] = "ARMED"
        
    except ValueError as e:
        result["error"] = str(e)
        result["status"] = "ERROR"
    
    return result
