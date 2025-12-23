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


# ======== V2 State Functions (Phase 6A.2) ========

def get_state_path_v2(stage: str, run_id: str, home_dir: str = None) -> Path:
    """Get path to SIM state v2 file."""
    base = Path(home_dir) if home_dir else Path("out/matrix_runs")
    return base / stage / run_id / "state" / "pool_portfolio_state_sim_v2.json"

def load_state_v2(stage: str, run_id: str, home_dir: str = None):
    """
    Load state v2 with migration from v1.
    
    Priority:
    1. If v2 exists: load
    2. If v1 exists: migrate
    3. Else: empty v2
    """
    from tezaver.matrix.pool.portfolio_models_v2 import (
        PortfolioStateV2,
        PortfolioPositionV2,
        PortfolioTotalsV2,
        empty_state_v2,
        compute_totals
    )
    
    # Try v2 first
    v2_path = get_state_path_v2(stage, run_id, home_dir)
    if v2_path.exists():
        data = read_json_safe(v2_path)
        if data:
            return PortfolioStateV2.from_dict(data)
    
    # Try v1 and migrate
    v1_path = get_state_path(stage, run_id, home_dir)
    if v1_path.exists():
        v1_data = read_json_safe(v1_path)
        if v1_data:
            return migrate_v1_to_v2(v1_data)
    
    # Empty state
    return empty_state_v2()

def migrate_v1_to_v2(v1_data: Dict[str, Any]):
    """Migrate v1 state to v2."""
    from tezaver.matrix.pool.portfolio_models_v2 import (
        PortfolioStateV2,
        PortfolioPositionV2,
        compute_totals
    )
    
    positions = []
    for p in v1_data.get("open_positions", []):
        pos = PortfolioPositionV2(
            pos_id=p.get("pos_id", ""),
            symbol=p.get("symbol", ""),
            timeframe=p.get("timeframe"),
            bundle_id=p.get("bundle_id"),
            status="OPEN",
            opened_ts_iso=p.get("opened_ts", now_iso()),
            closed_ts_iso=None,
            avg_entry=0.0,  # Unknown from v1
            qty=0.0,  # Unknown from v1
            notional_entry=0.0,  # Unknown from v1
            fees_paid=0.0,
            slippage_paid=0.0,
            realized_pnl=0.0,
            unrealized_pnl=0.0,
            last_mark_price=0.0,
            last_mark_ts_iso=now_iso()
        )
        positions.append(pos)
    
    totals = compute_totals(positions)
    return PortfolioStateV2(
        version="portfolio_state_sim_v2",
        updated_ts_iso=now_iso(),
        positions=positions,
        totals=totals
    )

def save_state_v2(state, stage: str, run_id: str, home_dir: str = None) -> str:
    """Save state v2 atomically."""
    import os
    path = get_state_path_v2(stage, run_id, home_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    tmp_path = path.with_suffix(".tmp")
    with open(tmp_path, "w") as f:
        json.dump(state.to_dict(), f, indent=2)
    
    os.replace(tmp_path, path)
    return str(path)

def update_position_on_open(
    state,
    pos_id: str,
    symbol: str,
    timeframe: str,
    bundle_id: str,
    avg_entry: float,
    qty: float,
    notional_entry: float,
    fee_cost: float,
    slippage_cost: float
):
    """Update/create position on OPEN fill."""
    from tezaver.matrix.pool.portfolio_models_v2 import PortfolioPositionV2, compute_totals
    
    pos = PortfolioPositionV2(
        pos_id=pos_id,
        symbol=symbol,
        timeframe=timeframe,
        bundle_id=bundle_id,
        status="OPEN",
        opened_ts_iso=now_iso(),
        closed_ts_iso=None,
        avg_entry=avg_entry,
        qty=qty,
        notional_entry=notional_entry,
        fees_paid=fee_cost,
        slippage_paid=slippage_cost,
        realized_pnl=0.0,
        unrealized_pnl=0.0,
        last_mark_price=avg_entry,
        last_mark_ts_iso=now_iso()
    )
    state.positions.append(pos)
    state.totals = compute_totals(state.positions)
    state.updated_ts_iso = now_iso()
    return state

def update_position_on_close(
    state,
    pos_id: str,
    close_eff_price: float,
    fee_cost: float,
    slippage_cost: float
):
    """Update position on CLOSE fill."""
    from tezaver.matrix.pool.portfolio_models_v2 import compute_totals
    
    for pos in state.positions:
        if pos.pos_id == pos_id and pos.status == "OPEN":
            # Compute realized PnL: (close_price - avg_entry) * qty - close_fee
            pnl_gross = (close_eff_price - pos.avg_entry) * pos.qty
            pnl_net = pnl_gross - fee_cost
            
            pos.realized_pnl = pnl_net
            pos.unrealized_pnl = 0.0
            pos.fees_paid += fee_cost
            pos.slippage_paid += slippage_cost
            pos.status = "CLOSED"
            pos.closed_ts_iso = now_iso()
            pos.last_mark_price = close_eff_price
            pos.last_mark_ts_iso = now_iso()
            break
    else:
        # No matching position found, try symbol match
        symbol = None
        for pos in state.positions:
            if pos.status == "OPEN":
                pos.realized_pnl = 0.0  # Can't compute without original
                pos.unrealized_pnl = 0.0
                pos.fees_paid += fee_cost
                pos.slippage_paid += slippage_cost
                pos.status = "CLOSED"
                pos.closed_ts_iso = now_iso()
                break
    
    state.totals = compute_totals(state.positions)
    state.updated_ts_iso = now_iso()
    return state

def mark_to_market(state, ref_price: float = 1.0):
    """Update unrealized PnL for open positions."""
    from tezaver.matrix.pool.portfolio_models_v2 import compute_totals
    
    for pos in state.positions:
        if pos.status == "OPEN":
            pos.unrealized_pnl = (ref_price - pos.avg_entry) * pos.qty
            pos.last_mark_price = ref_price
            pos.last_mark_ts_iso = now_iso()
    
    state.totals = compute_totals(state.positions)
    state.updated_ts_iso = now_iso()
    return state
