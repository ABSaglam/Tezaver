"""
Bundle Loader v1
=================

Scanner and loader for ApprovedRallyBundle v1 packages with QC enforcement.
"""

import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from tezaver.matrix.bundles.bundle_models_v1 import (
    ApprovedRallyBundleManifestV1,
    LoadedBundle
)
from tezaver.matrix.bundles.bundle_registry import BundleRegistry


def scan_bundles(root_path: str = ".tezaver_matrix/approved_bundles_v1") -> List[Path]:
    """
    Scan for bundle directories containing manifest.json.
    
    Args:
        root_path: Root directory for bundles
    
    Returns:
        List of bundle directory paths
    """
    root = Path(root_path)
    
    if not root.exists():
        return []
    
    # Find all manifest files
    manifest_files = list(root.glob("*/*/*/manifest.json"))
    
    # Return parent directories (bundle dirs)
    bundle_dirs = [f.parent for f in manifest_files]
    
    return bundle_dirs


def load_manifest(bundle_dir: Path) -> ApprovedRallyBundleManifestV1:
    """
    Load and validate manifest from bundle directory.
    
    Args:
        bundle_dir: Path to bundle directory
    
    Returns:
        Validated manifest
    
    Raises:
        ValueError: If manifest is invalid
        FileNotFoundError: If manifest.json not found
    """
    manifest_file = bundle_dir / "manifest.json"
    
    if not manifest_file.exists():
        raise FileNotFoundError(f"manifest.json not found in {bundle_dir}")
    
    with open(manifest_file, 'r') as f:
        data = json.load(f)
    
    return ApprovedRallyBundleManifestV1.from_dict(data)


def load_bundle(
    bundle_dir: Path,
    registry: Optional[BundleRegistry] = None,
    emit_telemetry: bool = True
) -> LoadedBundle:
    """
    Load bundle with QC enforcement and telemetry.
    
    Args:
        bundle_dir: Path to bundle directory
        registry: Optional registry to add bundle to
        emit_telemetry: Whether to emit telemetry events
    
    Returns:
        LoadedBundle instance
    """
    # Try to load manifest
    try:
        manifest = load_manifest(bundle_dir)
        status = "DISCOVERED"
        reject_reason = None
        
        # Emit BUNDLE_DISCOVERED
        if emit_telemetry:
            _emit_telemetry("BUNDLE_DISCOVERED", manifest, reject_reason)
        
        # QC Enforcement
        if manifest.qc_verdict != "PASS":
            status = "REJECTED"
            reject_reason = "QC_FAIL"
            
            # Emit BUNDLE_REJECTED
            if emit_telemetry:
                _emit_telemetry("BUNDLE_REJECTED", manifest, reject_reason)
        else:
            status = "LOADED_OK"
            
            # Emit BUNDLE_LOADED
            if emit_telemetry:
                _emit_telemetry("BUNDLE_LOADED", manifest, reject_reason)
        
    except ValueError as e:
        # Invalid manifest
        # Create minimal manifest stub for error tracking
        status = "REJECTED"
        reject_reason = str(e)
        
        # Create a minimal manifest for error case
        manifest = None
        
        if emit_telemetry:
            _emit_telemetry_error(bundle_dir, reject_reason)
    
    except Exception as e:
        # Other errors (file not found, JSON parse error, etc.)
        status = "REJECTED"
        reject_reason = f"LOAD_ERROR: {str(e)}"
        manifest = None
        
        if emit_telemetry:
            _emit_telemetry_error(bundle_dir, reject_reason)
    
    # Create LoadedBundle
    loaded = LoadedBundle(
        manifest=manifest,
        bundle_dir=str(bundle_dir),
        status=status,
        reject_reason=reject_reason
    )
    
    # Add to registry if provided
    if registry:
        registry.add(loaded)
    
    return loaded


def _emit_telemetry(event_type: str, manifest: ApprovedRallyBundleManifestV1, reject_reason: Optional[str]):
    """
    Emit telemetry event (simple print for now, can be extended to proper telemetry system).
    
    Args:
        event_type: BUNDLE_DISCOVERED | BUNDLE_LOADED | BUNDLE_REJECTED
        manifest: Bundle manifest
        reject_reason: Rejection reason if applicable
    """
    event = {
        "event_type": event_type,
        "ts": datetime.utcnow().isoformat(),
        "bundle_id": manifest.bundle_id,
        "symbol": manifest.symbol,
        "timeframe": manifest.timeframe,
        "event_id": manifest.event_id,
        "qc_verdict": manifest.qc_verdict,
        "qc_score": manifest.qc_score,
        "reject_reason": reject_reason
    }
    
    # Simple print telemetry (can be replaced with proper logging/telemetry)
    print(f"[TELEMETRY] {json.dumps(event)}")


def _emit_telemetry_error(bundle_dir: Path, reject_reason: str):
    """Emit telemetry for bundle load errors."""
    event = {
        "event_type": "BUNDLE_REJECTED",
        "ts": datetime.utcnow().isoformat(),
        "bundle_dir": str(bundle_dir),
        "reject_reason": reject_reason
    }
    
    print(f"[TELEMETRY] {json.dumps(event)}")


def load_all_bundles(
    root_path: str = ".tezaver_matrix/approved_bundles_v1",
    registry: Optional[BundleRegistry] = None
) -> List[LoadedBundle]:
    """
    Scan and load all bundles from root path.
    
    Args:
        root_path: Root directory for bundles
        registry: Optional registry to populate
    
    Returns:
        List of LoadedBundle instances
    """
    bundle_dirs = scan_bundles(root_path)
    
    loaded_bundles = []
    for bundle_dir in bundle_dirs:
        loaded = load_bundle(bundle_dir, registry=registry)
        loaded_bundles.append(loaded)
    
    return loaded_bundles
