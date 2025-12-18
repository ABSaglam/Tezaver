# Tezaver Bulut - Risk Tests
"""
Tests for Portfolio Risk Service (v0.12).
"""

import pytest
from unittest.mock import MagicMock
import time
from datetime import datetime, timezone

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.portfolio_risk import PortfolioRiskService
from tezaver.bulut.services.group_caps_loader import GroupCapsLoader

@pytest.fixture
def risk_config():
    return BulutConfig(
        daily_loss_limit_usdt=100.0,
        entry_halted_on_daily_loss=True,
        cooldown_cycles_after_sl=2, # Short cooldown
        max_open_positions=5,
        # Mock paths
        symbol_groups_path="mock/groups.json",
        group_caps_path="mock/caps.json"
    )

@pytest.fixture
def mock_db():
    db = MagicMock()
    # Defaults
    db.get_today_net_pnl.return_value = 0.0
    db.get_position.return_value = None
    db.get_open_positions.return_value = []
    return db

@pytest.fixture
def mock_groups():
    g = MagicMock()
    g.get_group.return_value = "default"
    g.get_cap.return_value = 1 # strict cap
    return g

@pytest.fixture
def risk_service(risk_config, mock_db, mock_groups):
    return PortfolioRiskService(risk_config, mock_db, mock_groups, telemetry=None)

def test_daily_loss_guard(risk_service, mock_db):
    """Test blocking when daily loss exceeded."""
    # 1. PnL = -50 (Limit -100) -> Allowed
    mock_db.get_today_net_pnl.return_value = -50.0
    allowed, code, _ = risk_service.check_entry_allowed("BTCUSDT", 100, time.time())
    assert allowed
    
    # 2. PnL = -150 (Limit -100) -> Blocked
    mock_db.get_today_net_pnl.return_value = -150.0
    allowed, code, _ = risk_service.check_entry_allowed("BTCUSDT", 100, time.time())
    assert not allowed
    assert code == "DAILY_LOSS_GUARD"

def test_cooldown_after_sl(risk_service, mock_db):
    """Test cooldown logic after SL exit."""
    mock_db.get_today_net_pnl.return_value = 0.0
    
    now = time.time()
    # Exit 1000s ago (approx 1 cycle = 900s)
    last_exit_ts = datetime.fromtimestamp(now - 1000, timezone.utc).isoformat()
    
    mock_db.get_position.return_value = {
        "status": "CLOSED",
        "last_exit_reason": "SL",
        "last_exit_ts": last_exit_ts
    }
    
    # Config: 2 cycles cooldown (1800s required)
    # Elapsed: 1000s -> Blocked
    allowed, code, meta = risk_service.check_entry_allowed("BTCUSDT", 100, now)
    assert not allowed
    assert code == "COOLDOWN_AFTER_SL"
    assert meta["remaining_cycles"] > 0
    
    # Exit 2000s ago -> Allowed
    last_exit_ts_old = datetime.fromtimestamp(now - 2000, timezone.utc).isoformat()
    mock_db.get_position.return_value = {
        "status": "CLOSED",
        "last_exit_reason": "SL",
        "last_exit_ts": last_exit_ts_old
    }
    allowed, code, _ = risk_service.check_entry_allowed("BTCUSDT", 100, now)
    assert allowed

def test_group_caps(risk_service, mock_db, mock_groups):
    """Test group limits."""
    mock_db.get_today_net_pnl.return_value = 0.0
    mock_db.get_position.return_value = None
    
    # Setup: Cap = 1 for "majors"
    mock_groups.get_group.side_effect = lambda sym: "majors" if sym in ["BTC", "ETH"] else "default"
    mock_groups.get_cap.side_effect = lambda grp: 1 if grp == "majors" else 5
    
    # 1. Existing pos: BTC (majors)
    mock_db.get_open_positions.return_value = [{"symbol": "BTC"}]
    
    # 2. Try enter ETH (majors) -> Blocked (1 >= 1)
    allowed, code, _ = risk_service.check_entry_allowed("ETH", 100, time.time())
    assert not allowed
    assert code == "GROUP_CAP_REACHED"
    
    # 3. Try enter SOL (default) -> Allowed
    allowed, code, _ = risk_service.check_entry_allowed("SOL", 100, time.time())
    assert allowed
