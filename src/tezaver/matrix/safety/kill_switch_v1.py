"""
Kill Switch V1
==============

Pool-level kill switch for blocking all OPEN/CLOSE actions.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _read_json_safe(path: Path) -> Dict[str, Any]:
    """Read JSON file safely."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

def get_kill_switch_state(
    home_path: str = None,
    stage: str = None,
    run_id: str = None
) -> Dict[str, Any]:
    """
    Get kill switch state.
    
    Priority:
    1. Env var TEZAVER_KILL_SWITCH="1"
    2. Run-scoped marker file
    3. Default: not triggered
    
    Args:
        home_path: Base path for runs
        stage: Run stage
        run_id: Run ID
        
    Returns:
        {"triggered": bool, "reason": str, "ts": str}
    """
    # Priority 1: Env var
    env_val = os.environ.get("TEZAVER_KILL_SWITCH", "").strip()
    if env_val == "1":
        return {
            "triggered": True,
            "reason": "env",
            "ts": now_iso()
        }
    
    # Priority 2: Run-scoped marker
    if home_path and stage and run_id:
        base = Path(home_path) if home_path else Path("out/matrix_runs")
        marker_path = base / stage / run_id / "state" / "pool_kill_switch_state_v1.json"
        marker = _read_json_safe(marker_path)
        if marker.get("triggered"):
            return {
                "triggered": True,
                "reason": marker.get("reason", "marker"),
                "ts": marker.get("ts", now_iso())
            }
    
    # Default: not triggered
    return {
        "triggered": False,
        "reason": None,
        "ts": now_iso()
    }

def write_kill_switch_marker(
    home_path: str,
    stage: str,
    run_id: str,
    triggered: bool = True,
    reason: str = "manual"
) -> str:
    """
    Write kill switch marker file.
    
    Args:
        home_path: Base path for runs
        stage: Run stage
        run_id: Run ID
        triggered: Kill switch state
        reason: Reason for activation
        
    Returns:
        Path to marker file
    """
    base = Path(home_path) if home_path else Path("out/matrix_runs")
    state_dir = base / stage / run_id / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    
    marker_path = state_dir / "pool_kill_switch_state_v1.json"
    data = {
        "triggered": triggered,
        "reason": reason,
        "ts": now_iso()
    }
    
    with open(marker_path, "w") as f:
        json.dump(data, f, indent=2)
    
    return str(marker_path)
