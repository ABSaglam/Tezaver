"""
Reconcile Engine V1
===================

Deterministic reconciliation logic for restart drift detection.
"""
from typing import Dict, Any, List, Tuple
import hashlib

def reconcile_positions_on_restart(
    before_snapshot: Dict[str, Any],
    after_snapshot: Dict[str, Any]
) -> Tuple[Dict[str, Any], str, List[str]]:
    """
    Compare before and after position snapshots to detect drift.
    
    Args:
        before_snapshot: {"positions":[...], "count":int}
        after_snapshot: {"positions":[...], "count":int}
        
    Returns:
        (drift_dict, verdict, suggested_actions)
    """
    before_positions = before_snapshot.get("positions", [])
    after_positions = after_snapshot.get("positions", [])
    
    # Extract IDs (use pos_id if available, else (symbol,tf) tuple)
    def get_id(pos: Dict[str, Any]) -> str:
        if "pos_id" in pos:
            return pos["pos_id"]
        return f"{pos.get('symbol', 'UNK')}|{pos.get('timeframe', 'UNK')}"
    
    before_ids = set(get_id(p) for p in before_positions)
    after_ids = set(get_id(p) for p in after_positions)
    
    missing_ids = list(before_ids - after_ids)
    extra_ids = list(after_ids - before_ids)
    
    changed = bool(missing_ids or extra_ids)
    delta_count = len(after_positions) - len(before_positions)
    
    drift = {
        "changed": changed,
        "delta_count": delta_count,
        "missing_ids": missing_ids,
        "extra_ids": extra_ids
    }
    
    if not changed:
        verdict = "OK"
        suggested_actions = []
    else:
        verdict = "NEEDS_SAFE_MODE"
        suggested_actions = [
            "ENTER_SAFE_MODE",
            "RECONCILE_POSITIONS",
            "BLOCK_NEW_ENTRIES_UNTIL_RECONCILED"
        ]
        
    return drift, verdict, suggested_actions

def generate_reconcile_id(run_id: str, before_count: int, after_count: int) -> str:
    """Generate deterministic reconcile ID."""
    raw = f"{run_id}|{before_count}|{after_count}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]
