# Tezaver Bulut - Portfolio Risk v1 Tests
"""
Tests for Portfolio Risk Service (v0.12).
Scenarios:
1. Daily Loss Guard Block
2. Cooldown Block
3. Group Cap Block
"""

import pytest
from unittest.mock import MagicMock
import time
from datetime import datetime, timezone

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.portfolio_risk import PortfolioRiskService

@pytest.fixture
def risk_config():
    return BulutConfig(
        daily_loss_limit_usdt=200.0,
        entry_halted_on_daily_loss=True,
        cooldown_cycles_after_sl=8, # 2 hours
        max_open_positions=5,
        symbol_groups_path="mock/groups.json",
        group_caps_path="mock/caps.json"
    )

@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_today_net_pnl_utc.return_value = 0.0
    db.get_position.return_value = None
    db.get_open_positions.return_value = []
    # get_today_net_pnl_utc needs to match service calls
    return db

@pytest.fixture
def mock_groups():
    g = MagicMock()
    g.get_group.return_value = "default"
    g.get_cap.return_value = 1
    g.get_open_counts.return_value = {}
    return g

@pytest.fixture
def mock_telemetry():
    t = MagicMock()
    return t

@pytest.fixture
def risk_service(risk_config, mock_db, mock_groups, mock_telemetry):
    return PortfolioRiskService(risk_config, mock_db, mock_groups, mock_telemetry)

def test_daily_loss_guard(risk_service, mock_db):
    """Test blocking when daily loss exceeded."""
    # 1. PnL = -100 (Limit -200) -> Allowed
    mock_db.get_today_net_pnl_utc.return_value = -100.0
    allowed, code, _ = risk_service.check_entry_allowed("BTCUSDT", 100, time.time())
    assert allowed
    
    # 2. PnL = -200.1 (Limit -200) -> Blocked
    mock_db.get_today_net_pnl_utc.return_value = -200.1
    allowed, code, details = risk_service.check_entry_allowed("BTCUSDT", 100, time.time())
    assert not allowed
    assert code == "DAILY_LOSS_GUARD"
    assert details["limit"] == -200.0

def test_cooldown_after_sl(risk_service, mock_db):
    """Test cooldown logic after SL exit."""
    mock_db.get_today_net_pnl_utc.return_value = 0.0
    
    now = time.time()
    # 8 cycles * 15m = 120m = 7200s
    # Exit 1000s ago -> Block
    # Exit 8000s ago -> Allow
    
    last_exit_ts = datetime.fromtimestamp(now - 1000, timezone.utc).isoformat()
    
    mock_db.get_position.return_value = {
        "status": "CLOSED",
        "last_exit_reason": "SL",
        "last_exit_cycle_ts": last_exit_ts
    }
    
    allowed, code, meta = risk_service.check_entry_allowed("BTCUSDT", 100, now)
    assert not allowed
    assert code == "COOLDOWN_AFTER_SL"
    
    # Check Manual exit -> Allowed
    mock_db.get_position.return_value = {
        "status": "CLOSED",
        "last_exit_reason": "MANUAL",
        "last_exit_cycle_ts": last_exit_ts
    }
    allowed, code, _ = risk_service.check_entry_allowed("BTCUSDT", 100, now)
    assert allowed

def test_group_caps(risk_service, mock_db, mock_groups):
    """Test group limits."""
    mock_db.get_today_net_pnl_utc.return_value = 0.0
    
    # Setup: Cap = 1 for "majors"
    mock_groups.get_group.return_value = "majors"
    mock_groups.get_cap.return_value = 1
    
    # 1. Mock DB returns open positions
    # 2. Mock groups returns open counts based on positions
    # But service calls `groups.get_open_counts(positions)`
    # Which calls `self.get_group` internally?
    # In Mock, `get_open_counts` is mocked directly?
    # Service calls: `group_counts = self._groups.get_open_counts(open_positions)`
    
    mock_groups.get_open_counts.return_value = {"majors": 1}
    
    # Try enter -> Blocked (1 >= 1)
    allowed, code, _ = risk_service.check_entry_allowed("ETH", 100, time.time())
    assert not allowed
    assert code == "GROUP_CAP_REACHED"
    
    # 3. Cap disabled (0)
    mock_groups.get_cap.return_value = 0
    allowed, code, _ = risk_service.check_entry_allowed("ETH", 100, time.time())
    assert not allowed
    assert code == "GROUP_DISABLED"
