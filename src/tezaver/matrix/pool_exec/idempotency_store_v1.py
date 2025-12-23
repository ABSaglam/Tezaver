"""
Idempotency Store V1
====================

Order key store for preventing duplicate execution.
"""
import json
import os
from pathlib import Path
from typing import Set, Dict, Any
from datetime import datetime, timezone

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _get_store_path(stage: str, run_id: str, home_dir: str = None) -> Path:
    """Get path to idempotency keys file."""
    base = Path(home_dir) if home_dir else Path("out/matrix_runs")
    return base / stage / run_id / "state" / "pool_idempotency_keys_v1.json"

def load_keys(stage: str, run_id: str, home_dir: str = None) -> Set[str]:
    """
    Load idempotency keys from store.
    
    Args:
        stage: Run stage
        run_id: Run ID
        home_dir: Optional home directory
        
    Returns:
        Set of order_keys
    """
    path = _get_store_path(stage, run_id, home_dir)
    if not path.exists():
        return set()
    
    try:
        with open(path) as f:
            data = json.load(f)
            return set(data.get("keys", []))
    except Exception:
        return set()

def has_key(stage: str, run_id: str, key: str, home_dir: str = None) -> bool:
    """Check if order_key already exists."""
    keys = load_keys(stage, run_id, home_dir)
    return key in keys

def add_key(stage: str, run_id: str, key: str, home_dir: str = None) -> str:
    """
    Add order_key to store atomically.
    
    Args:
        stage: Run stage
        run_id: Run ID
        key: Order key to add
        home_dir: Optional home directory
        
    Returns:
        Path to store file
    """
    path = _get_store_path(stage, run_id, home_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing keys
    keys = load_keys(stage, run_id, home_dir)
    keys.add(key)
    
    data = {
        "run_id": run_id,
        "stage": stage,
        "keys": list(keys),
        "updated_ts_iso": now_iso()
    }
    
    # Atomic write: temp then rename
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    
    os.replace(tmp_path, path)
    
    return str(path)

def add_keys_batch(stage: str, run_id: str, keys_to_add: Set[str], home_dir: str = None) -> str:
    """Add multiple keys at once (atomic)."""
    path = _get_store_path(stage, run_id, home_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    existing = load_keys(stage, run_id, home_dir)
    existing.update(keys_to_add)
    
    data = {
        "run_id": run_id,
        "stage": stage,
        "keys": list(existing),
        "updated_ts_iso": now_iso()
    }
    
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
    
    os.replace(tmp_path, path)
    
    return str(path)

def keys_count(stage: str, run_id: str, home_dir: str = None) -> int:
    """Get count of stored keys."""
    return len(load_keys(stage, run_id, home_dir))
