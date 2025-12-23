import pytest
import json
from pathlib import Path
from tezaver.matrix.pool.portfolio_state_store_sim_v1 import (
    apply_intents_to_state,
    generate_pos_id,
    save_sim_state,
    load_sim_state
)
from tezaver.matrix.pool.portfolio_provider_v2 import PortfolioProviderV2

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)

def test_empty_snapshot(tmp_path):
    """Empty state -> open_now=0 capacity=20."""
    provider = PortfolioProviderV2(mode="EMPTY", home_dir=str(tmp_path))
    
    snapshot = provider.get_snapshot("war", "run_empty", max_open_positions=20)
    
    assert snapshot.open_now == 0
    assert snapshot.capacity == 20
    assert snapshot.source == "EMPTY"

def test_sim_state_with_positions(tmp_path):
    """SIM state with 5 positions -> open_now=5 capacity=15."""
    # Create SIM state with 5 positions
    state = {
        "open_positions": [
            {"pos_id": f"pos_{i}", "symbol": f"SYM{i}"} for i in range(5)
        ],
        "open_orders": []
    }
    
    state_dir = tmp_path / "war" / "run_sim5" / "state"
    state_dir.mkdir(parents=True)
    write_json(state_dir / "pool_portfolio_state_sim_v1.json", state)
    
    provider = PortfolioProviderV2(mode="SIM_STATE", home_dir=str(tmp_path))
    
    snapshot = provider.get_snapshot("war", "run_sim5", max_open_positions=20)
    
    assert snapshot.open_now == 5
    assert snapshot.capacity == 15
    assert snapshot.source == "SIM_STATE"

def test_deterministic_pos_id():
    """pos_id is deterministic based on order_key."""
    intents = [
        {"action": "OPEN_POSITION", "order_key": "key_abc", "symbol": "BTC"},
        {"action": "OPEN_POSITION", "order_key": "key_abc", "symbol": "BTC"}  # Same key
    ]
    
    # Apply twice
    state1 = apply_intents_to_state(intents[:1])
    state2 = apply_intents_to_state(intents[:1])
    
    assert state1["open_positions"][0]["pos_id"] == state2["open_positions"][0]["pos_id"]
    
    # pos_id is hash of order_key
    expected_pos_id = generate_pos_id("key_abc")
    assert state1["open_positions"][0]["pos_id"] == expected_pos_id

def test_close_removes_position():
    """CLOSE_POSITION intent removes matching position."""
    intents = [
        {"action": "OPEN_POSITION", "order_key": "key_1", "symbol": "BTC"},
        {"action": "OPEN_POSITION", "order_key": "key_2", "symbol": "ETH"},
        {"action": "CLOSE_POSITION", "order_key": "key_3", "symbol": "BTC"}
    ]
    
    state = apply_intents_to_state(intents)
    
    # BTC closed, ETH remains
    assert len(state["open_positions"]) == 1
    assert state["open_positions"][0]["symbol"] == "ETH"

def test_capacity_respects_max(tmp_path):
    """Capacity calculation respects max_open_positions."""
    # 18 positions, max=20 -> capacity=2
    state = {
        "open_positions": [
            {"pos_id": f"pos_{i}", "symbol": f"SYM{i}"} for i in range(18)
        ],
        "open_orders": []
    }
    
    state_dir = tmp_path / "war" / "run_cap" / "state"
    state_dir.mkdir(parents=True)
    write_json(state_dir / "pool_portfolio_state_sim_v1.json", state)
    
    provider = PortfolioProviderV2(mode="SIM_STATE", home_dir=str(tmp_path))
    
    snapshot = provider.get_snapshot("war", "run_cap", max_open_positions=20)
    
    assert snapshot.open_now == 18
    assert snapshot.capacity == 2
