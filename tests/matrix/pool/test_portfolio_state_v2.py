import pytest
import json
from pathlib import Path
from tezaver.matrix.pool.portfolio_models_v2 import (
    PortfolioPositionV2,
    PortfolioStateV2,
    PortfolioTotalsV2,
    compute_totals,
    empty_state_v2
)
from tezaver.matrix.pool.portfolio_state_store_sim_v1 import (
    load_state_v2,
    save_state_v2,
    update_position_on_open,
    update_position_on_close,
    migrate_v1_to_v2
)

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)

def test_open_creates_position_with_avg_entry_qty(tmp_path):
    """OPEN creates position with avg_entry and qty."""
    state = empty_state_v2()
    
    state = update_position_on_open(
        state=state,
        pos_id="pos_abc",
        symbol="BTC",
        timeframe="1h",
        bundle_id="b1",
        avg_entry=100.08,  # eff_price
        qty=0.9992,
        notional_entry=100.0,
        fee_cost=0.04,
        slippage_cost=0.08
    )
    
    assert len(state.positions) == 1
    pos = state.positions[0]
    assert pos.pos_id == "pos_abc"
    assert pos.status == "OPEN"
    assert abs(pos.avg_entry - 100.08) < 1e-6
    assert abs(pos.qty - 0.9992) < 1e-6
    assert abs(pos.fees_paid - 0.04) < 1e-6
    assert abs(pos.slippage_paid - 0.08) < 1e-6
    
    assert state.totals.open_positions == 1

def test_close_realizes_pnl(tmp_path):
    """CLOSE realizes PnL."""
    state = empty_state_v2()
    
    # Open at 100.08
    state = update_position_on_open(
        state=state,
        pos_id="pos_pnl",
        symbol="BTC",
        timeframe="1h",
        bundle_id="b1",
        avg_entry=100.08,
        qty=0.9992,
        notional_entry=100.0,
        fee_cost=0.04,
        slippage_cost=0.08
    )
    
    # Close at 109.912 (110 * (1 - 0.0008) for CLOSE)
    close_eff_price = 109.912
    state = update_position_on_close(
        state=state,
        pos_id="pos_pnl",
        close_eff_price=close_eff_price,
        fee_cost=0.044,  # ~110 * 0.0004
        slippage_cost=0.088
    )
    
    pos = state.positions[0]
    assert pos.status == "CLOSED"
    
    # pnl_gross = (109.912 - 100.08) * 0.9992 ≈ 9.824
    # pnl_net = 9.824 - 0.044 ≈ 9.78
    expected_pnl = (close_eff_price - 100.08) * 0.9992 - 0.044
    assert abs(pos.realized_pnl - expected_pnl) < 0.01
    
    assert state.totals.open_positions == 0
    assert state.totals.realized_pnl > 0

def test_migration_v1_to_v2(tmp_path):
    """v1 state migrates to v2."""
    # Create v1 state
    v1_data = {
        "open_positions": [
            {"pos_id": "pos_old", "symbol": "ETH", "timeframe": "4h", "opened_ts": "2023-01-01"}
        ],
        "open_orders": [],
        "updated_ts": "2023-01-01"
    }
    
    v2_state = migrate_v1_to_v2(v1_data)
    
    assert v2_state.version == "portfolio_state_sim_v2"
    assert len(v2_state.positions) == 1
    assert v2_state.positions[0].pos_id == "pos_old"
    assert v2_state.positions[0].status == "OPEN"
    assert v2_state.positions[0].avg_entry == 0.0  # Unknown from v1

def test_load_state_v2_priority(tmp_path):
    """load_state_v2 loads v2 over v1."""
    state_dir = tmp_path / "war" / "run_prio" / "state"
    state_dir.mkdir(parents=True)
    
    # Create v1 state
    v1 = {"open_positions": [{"pos_id": "v1_pos"}], "updated_ts": "2023-01-01"}
    write_json(state_dir / "pool_portfolio_state_sim_v1.json", v1)
    
    # Create v2 state
    v2 = {"version": "portfolio_state_sim_v2", "positions": [], "totals": {}, "updated_ts_iso": "2024-01-01"}
    write_json(state_dir / "pool_portfolio_state_sim_v2.json", v2)
    
    loaded = load_state_v2("war", "run_prio", str(tmp_path))
    
    # Should load v2, not v1
    assert loaded.version == "portfolio_state_sim_v2"
    assert len(loaded.positions) == 0  # v2 is empty
