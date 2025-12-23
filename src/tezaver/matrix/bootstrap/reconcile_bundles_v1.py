"""
Reconcile Bundles v1
====================

Boot-time bundle reconciliation for Matrix.
Rebuilds registry from disk on restart for deterministic state.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, Callable

from tezaver.matrix.bundles.bundle_loader_v1 import load_all_bundles
from tezaver.matrix.bundles.bundle_registry import BundleRegistry


def reconcile_bundles_on_boot(
    root_path: str,
    registry: BundleRegistry,
    emit: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Reconcile bundles on boot by rescanning disk and rebuilding registry.
    
    This function provides deterministic restart behavior:
    - Clears existing registry state
    - Rescans bundle root from disk
    - Reloads all bundles with QC validation
    - Emits telemetry for tracking
    
    Args:
        root_path: Path to approved_bundles_v1 root directory
        registry: BundleRegistry to rebuild
        emit: Optional callback for telemetry emission
    
    Returns:
        Dictionary with reconciliation result:
        - status: str (OK | ERROR)
        - counts: Dict[str, int] (loaded_ok, rejected, total)
        - duration_ms: int
        - error: Optional[str]
    """
    start_ts = datetime.now(timezone.utc)
    start_time = time.time()
    
    result = {
        "status": "ERROR",
        "counts": None,
        "duration_ms": 0,
        "root_path": root_path,
        "error": None
    }
    
    # Emit start event
    start_event = {
        "event_type": "BOOT_RECONCILE_STARTED",
        "ts": start_ts.isoformat(),
        "root_path": root_path
    }
    
    if emit:
        emit(start_event)
    else:
        print(f"[TELEMETRY] {json.dumps(start_event)}")
    
    try:
        # Reset registry
        registry.reset()
        
        # Check if root exists
        root = Path(root_path)
        if not root.exists():
            result["status"] = "OK"
            result["counts"] = {"loaded_ok": 0, "rejected": 0, "discovered": 0, "total": 0}
            result["duration_ms"] = int((time.time() - start_time) * 1000)
            
            # Emit done event with empty counts
            _emit_done_event(result, emit)
            registry.mark_reconciled(result["counts"])
            return result
        
        # Load all bundles
        load_all_bundles(root_path=root_path, registry=registry)
        
        # Get counts
        counts = registry.counts()
        result["counts"] = counts
        result["status"] = "OK"
        result["duration_ms"] = int((time.time() - start_time) * 1000)
        
        # Mark registry as reconciled
        registry.mark_reconciled(counts)
        
        # Emit done event
        _emit_done_event(result, emit)
        
    except Exception as e:
        result["error"] = str(e)
        result["status"] = "ERROR"
        result["duration_ms"] = int((time.time() - start_time) * 1000)
        
        # Emit error event
        error_event = {
            "event_type": "BOOT_RECONCILE_ERROR",
            "ts": datetime.now(timezone.utc).isoformat(),
            "root_path": root_path,
            "error": str(e),
            "duration_ms": result["duration_ms"]
        }
        
        if emit:
            emit(error_event)
        else:
            print(f"[TELEMETRY] {json.dumps(error_event)}")
    
    return result


def _emit_done_event(result: Dict[str, Any], emit: Optional[Callable]) -> None:
    """Emit BOOT_RECONCILE_DONE event."""
    done_event = {
        "event_type": "BOOT_RECONCILE_DONE",
        "ts": datetime.now(timezone.utc).isoformat(),
        "root_path": result["root_path"],
        "status": result["status"],
        "counts": result["counts"],
        "duration_ms": result["duration_ms"]
    }
    
    if emit:
        emit(done_event)
    else:
        print(f"[TELEMETRY] {json.dumps(done_event)}")


# =============================================================================
# Global Registry and Boot Hook
# =============================================================================

# Global registry instance for Matrix
_global_registry: Optional[BundleRegistry] = None


def get_global_registry() -> BundleRegistry:
    """
    Get or create the global bundle registry.
    
    Returns:
        Global BundleRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = BundleRegistry()
    return _global_registry


def boot_reconcile_bundles(
    home_path: str = ".tezaver_matrix",
    emit: Optional[Callable[[Dict[str, Any]], None]] = None
) -> Dict[str, Any]:
    """
    Boot hook for bundle reconciliation.
    
    Called during Matrix startup to rebuild registry from disk.
    
    Args:
        home_path: Matrix home directory (default: .tezaver_matrix)
        emit: Optional telemetry callback
    
    Returns:
        Reconciliation result
    """
    registry = get_global_registry()
    root_path = str(Path(home_path) / "approved_bundles_v1")
    
    return reconcile_bundles_on_boot(
        root_path=root_path,
        registry=registry,
        emit=emit
    )
