# Tezaver Bulut - Risk Tests
"""
Tests for Portfolio Risk Service (v0.12).
"""

import pytest
from unittest.mock import MagicMock
import time
from datetime import datetime, timezone

from tezaver.bulut.services.portfolio_risk import PortfolioRiskService


@pytest.fixture
def mock_db():
    db = MagicMock()
    # Must use exact method names from portfolio_risk.py
    db.get_today_net_pnl_utc.return_value = 0.0  # Correct method name
    db.get_today_income_sum_utc.return_value = {"TOTAL": 0.0}  # Returns dict with TOTAL
    db.get_position.return_value = None
    db.get_open_positions.return_value = []
    return db


@pytest.fixture
def mock_groups():
    g = MagicMock()
    g.get_group.return_value = "default"
    g.get_cap.return_value = 1  # strict cap
    g.get_open_counts.return_value = {}  # Dict of group -> count
    return g


@pytest.fixture
def mock_telemetry():
    t = MagicMock()
    t.emit_custom = MagicMock()
    return t


@pytest.fixture
def risk_service(cfg, mock_db, mock_groups, mock_telemetry):
    """Use cfg from conftest (default BulutConfig)."""
    return PortfolioRiskService(cfg, mock_db, mock_groups, telemetry=mock_telemetry)


def test_daily_loss_guard(risk_service, mock_db):
    """Test blocking when daily loss exceeded."""
    # 1. PnL = -50 (Limit -200 default) -> Allowed
    mock_db.get_today_net_pnl_utc.return_value = -50.0
    allowed, code, _ = risk_service.check_entry_allowed("BTCUSDT", 100, time.time())
    assert allowed
    
    # 2. PnL = -250 (Limit -200) -> Blocked
    mock_db.get_today_net_pnl_utc.return_value = -250.0
    allowed, code, _ = risk_service.check_entry_allowed("BTCUSDT", 100, time.time())
    assert not allowed
    assert code == "DAILY_LOSS_GUARD"


def test_cooldown_after_sl(risk_service, mock_db):
    """Test cooldown logic after SL exit."""
    mock_db.get_today_net_pnl.return_value = 0.0
    
    now = time.time()
    # Exit 1000s ago (config default: 8 cycles = 7200s)
    last_exit_ts = datetime.fromtimestamp(now - 1000, timezone.utc).isoformat()
    
    mock_db.get_position.return_value = {
        "status": "CLOSED",
        "last_exit_reason": "SL",
        "last_exit_cycle_ts": last_exit_ts  # Correct field name
    }
    
    # Elapsed: 1000s < 7200s -> Blocked
    allowed, code, meta = risk_service.check_entry_allowed("BTCUSDT", 100, now)
    assert not allowed
    assert code == "COOLDOWN_AFTER_SL"
    
    # Exit 8000s ago -> Allowed
    last_exit_ts_old = datetime.fromtimestamp(now - 8000, timezone.utc).isoformat()
    mock_db.get_position.return_value = {
        "status": "CLOSED",
        "last_exit_reason": "SL",
        "last_exit_cycle_ts": last_exit_ts_old  # Correct field name
    }
    allowed, code, _ = risk_service.check_entry_allowed("BTCUSDT", 100, now)
    assert allowed


def test_group_caps(risk_service, mock_db, mock_groups):
    """Test group limits."""
    mock_db.get_today_net_pnl_utc.return_value = 0.0
    mock_db.get_position.return_value = None
    
    # Setup: Cap = 1 for "majors"
    mock_groups.get_group.side_effect = lambda sym: "majors" if sym in ["BTC", "ETH"] else "default"
    mock_groups.get_cap.side_effect = lambda grp: 1 if grp == "majors" else 5
    
    # 1. Existing pos: BTC (majors) - must configure get_open_counts
    mock_db.get_open_positions.return_value = [{"symbol": "BTC"}]
    mock_groups.get_open_counts.return_value = {"majors": 1, "default": 0}  # One open in majors
    
    # 2. Try enter ETH (majors) -> Blocked (1 >= 1)
    allowed, code, _ = risk_service.check_entry_allowed("ETH", 100, time.time())
    assert not allowed
    assert code == "GROUP_CAP_REACHED"
    
    # 3. Try enter SOL (default) - reset counts
    mock_groups.get_open_counts.return_value = {"majors": 1, "default": 0}
    allowed, code, _ = risk_service.check_entry_allowed("SOL", 100, time.time())
    assert allowed
