"""
Portfolio State Store SIM V1
============================

SIM state store for tracking open positions from execution intents.
"""
import json
import hashlib
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def write_json(path: Path, data: Dict[str, Any]):
    """Write JSON safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def read_json_safe(path: Path) -> Dict[str, Any]:
    """Read JSON file safely."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

def generate_pos_id(order_key: str) -> str:
    """Generate deterministic pos_id from order_key."""
    return hashlib.sha1(order_key.encode()).hexdigest()[:12]

def get_state_path(stage: str, run_id: str, home_dir: str = None) -> Path:
    """Get path to SIM state file."""
    base = Path(home_dir) if home_dir else Path("out/matrix_runs")
    return base / stage / run_id / "state" / "pool_portfolio_state_sim_v1.json"

def init_state() -> Dict[str, Any]:
    """Initialize empty state."""
    return {
        "open_positions": [],
        "open_orders": [],
        "updated_ts": now_iso()
    }

def apply_intents_to_state(
    intents: List[Dict[str, Any]],
    state: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Apply intents to state (OPEN adds, CLOSE removes).
    
    Args:
        intents: List of order intents
        state: Current state (or None for fresh)
        
    Returns:
        Updated state
    """
    if state is None:
        state = init_state()
    
    open_positions = state.get("open_positions", [])
    
    for intent in intents:
        action = intent.get("action")
        order_key = intent.get("order_key", "")
        
        if action == "OPEN_POSITION":
            pos_id = generate_pos_id(order_key)
            pos = {
                "pos_id": pos_id,
                "symbol": intent.get("symbol", "UNK"),
                "timeframe": intent.get("timeframe"),
                "opened_by_order_key": order_key,
                "opened_ts": now_iso(),
                "bundle_id": intent.get("bundle_id")
            }
            open_positions.append(pos)
            
        elif action == "CLOSE_POSITION":
            # Find position to close by symbol (or meta.pos_id if available)
            symbol = intent.get("symbol", "UNK")
            meta_pos_id = intent.get("meta", {}).get("pos_id")
            
            if meta_pos_id:
                # Exact match by pos_id
                open_positions = [p for p in open_positions if p.get("pos_id") != meta_pos_id]
            else:
                # Match by symbol (removes first match)
                for i, p in enumerate(open_positions):
                    if p.get("symbol") == symbol:
                        open_positions.pop(i)
                        break
    
    state["open_positions"] = open_positions
    state["updated_ts"] = now_iso()
    return state

def save_sim_state(stage: str, run_id: str, state: Dict[str, Any], home_dir: str = None):
    """Save SIM state to file."""
    path = get_state_path(stage, run_id, home_dir)
    write_json(path, state)
    return str(path)

def load_sim_state(stage: str, run_id: str, home_dir: str = None) -> Dict[str, Any]:
    """Load SIM state from file."""
    path = get_state_path(stage, run_id, home_dir)
    return read_json_safe(path) or init_state()
