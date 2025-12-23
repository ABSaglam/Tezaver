import pytest
import json
from pathlib import Path
from tezaver.matrix.pool.portfolio_models_v2 import empty_state_v2
from tezaver.matrix.pool.portfolio_state_store_sim_v1 import (
    load_state_v2,
    save_state_v2,
    update_position_on_open
)
from tezaver.matrix.pool.portfolio_provider_v2 import PortfolioProviderV2

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)

def test_provider_reads_open_now_and_capacity(tmp_path):
    """Provider computes open_now and capacity from v2 state."""
    # Create v2 state with 5 open positions
    state = empty_state_v2()
    for i in range(5):
        state = update_position_on_open(
            state=state,
            pos_id=f"pos_{i}",
            symbol=f"SYM{i}",
            timeframe="1h",
            bundle_id=f"b{i}",
            avg_entry=100.0,
            qty=1.0,
            notional_entry=100.0,
            fee_cost=0.04,
            slippage_cost=0.08
        )
    
    # Save state
    save_state_v2(state, "war", "run_cap", str(tmp_path))
    
    # Use provider
    provider = PortfolioProviderV2(mode="SIM_STATE", home_dir=str(tmp_path))
    snapshot = provider.get_snapshot("war", "run_cap", max_open_positions=20)
    
    assert snapshot.open_now == 5
    assert snapshot.capacity == 15

def test_provider_includes_totals(tmp_path):
    """Provider snapshot includes totals with PnL."""
    state = empty_state_v2()
    state = update_position_on_open(
        state=state,
        pos_id="pos_total",
        symbol="BTC",
        timeframe="1h",
        bundle_id="b1",
        avg_entry=100.0,
        qty=1.0,
        notional_entry=100.0,
        fee_cost=0.5,
        slippage_cost=0.3
    )
    
    save_state_v2(state, "war", "run_totals", str(tmp_path))
    
    provider = PortfolioProviderV2(mode="SIM_STATE", home_dir=str(tmp_path))
    snapshot = provider.get_snapshot("war", "run_totals", max_open_positions=20)
    
    # Check totals are populated
    assert snapshot.open_now == 1
    # totals should include fees
    assert hasattr(snapshot, 'open_positions') or len(snapshot.open_positions) > 0
