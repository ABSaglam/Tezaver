import pytest
from tezaver.matrix.pool_exec.sim_fill_model_v1 import (
    apply_bps,
    compute_fee,
    compute_slippage_cost,
    simulate_fill,
    DEFAULT_FEE_BPS,
    DEFAULT_SLIPPAGE_BPS
)

def test_apply_bps_open():
    """OPEN_POSITION applies slippage upwards (worse for user)."""
    result = apply_bps(100.0, 8.0, "OPEN_POSITION")
    # 100 * (1 + 8/10000) = 100.08
    assert abs(result - 100.08) < 1e-6

def test_apply_bps_close():
    """CLOSE_POSITION applies slippage downwards (worse for user)."""
    result = apply_bps(100.0, 8.0, "CLOSE_POSITION")
    # 100 * (1 - 8/10000) = 99.92
    assert abs(result - 99.92) < 1e-6

def test_compute_fee():
    """Fee computed correctly from notional and bps."""
    # 100 * 4/10000 = 0.04
    result = compute_fee(100.0, 4.0)
    assert abs(result - 0.04) < 1e-6

def test_compute_slippage_cost():
    """Slippage cost computed correctly."""
    # ref=100, eff=100.08, notional=100
    # slippage_cost = 0.08/100 * 100 = 0.08
    result = compute_slippage_cost(100.0, 100.08, 100.0)
    assert abs(result - 0.08) < 1e-6

def test_simulate_fill_open():
    """Simulate fill for OPEN_POSITION."""
    fill = simulate_fill(
        order_key="k1",
        intent_id="i1",
        action="OPEN_POSITION",
        symbol="BTCUSDT",
        timeframe="1h",
        ref_price=100.0,
        notional=100.0,
        fee_bps=4.0,
        slippage_bps=8.0
    )
    
    assert fill.ref_price == 100.0
    assert abs(fill.eff_price - 100.08) < 1e-6
    assert abs(fill.fee_cost - 0.04) < 1e-6
    assert abs(fill.slippage_cost - 0.08) < 1e-6
    # qty = 100 / 100.08 ≈ 0.9992
    assert abs(fill.qty - 100.0/100.08) < 1e-6

def test_simulate_fill_close():
    """Simulate fill for CLOSE_POSITION."""
    fill = simulate_fill(
        order_key="k2",
        intent_id="i2",
        action="CLOSE_POSITION",
        symbol="ETHUSDT",
        timeframe="4h",
        ref_price=50.0,
        notional=200.0,
        fee_bps=4.0,
        slippage_bps=8.0
    )
    
    # eff_price = 50 * (1 - 8/10000) = 49.96
    assert abs(fill.eff_price - 49.96) < 1e-6
    # fee_cost = 200 * 4/10000 = 0.08
    assert abs(fill.fee_cost - 0.08) < 1e-6
