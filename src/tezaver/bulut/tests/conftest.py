"""
Tezaver Bulut - Shared Test Fixtures (conftest.py)
Provides standardized fixtures for config, DB, and mocks.
"""
import pytest
import os
import dataclasses
from pathlib import Path
from unittest.mock import MagicMock

from tezaver.bulut.core.config import BulutConfig, reload_config
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence


# --- Config Fixtures ---

def make_config(**overrides) -> BulutConfig:
    """
    Create a BulutConfig with optional overrides.
    Since BulutConfig is frozen, we use dataclasses.replace.
    Invalid keys are silently ignored (frozen dataclass won't accept them anyway).
    """
    base = BulutConfig()
    
    # Filter to only valid fields
    valid_fields = {f.name for f in dataclasses.fields(BulutConfig)}
    filtered = {k: v for k, v in overrides.items() if k in valid_fields}
    
    if filtered:
        return dataclasses.replace(base, **filtered)
    return base


@pytest.fixture
def cfg():
    """Default config fixture."""
    return make_config()


@pytest.fixture
def cfg_test_mode():
    """Config with test-friendly settings."""
    return make_config(
        execution_enabled=False,
        startup_selftest_enabled=False,
        proof_ladder_auto_evaluate_enabled=False,
    )


# --- DB Fixtures ---

@pytest.fixture
def temp_db(tmp_path):
    """
    Temporary SQLite database fixture.
    Uses file-based DB (not :memory:) to avoid locking issues.
    Runs _init_db to ensure all tables exist.
    """
    db_path = tmp_path / "test_bulut.db"
    persistence = SqlitePersistence(str(db_path))
    persistence._init_db()
    
    yield persistence
    
    # Cleanup
    try:
        if hasattr(persistence, '_conn') and persistence._conn:
            persistence._conn.close()
    except Exception:
        pass


@pytest.fixture
def temp_db_path(tmp_path):
    """Just returns a path for tests that need to create their own persistence."""
    return str(tmp_path / "test.db")


# --- Mock Fixtures ---

@pytest.fixture
def mock_telemetry():
    """Standard telemetry mock."""
    mock = MagicMock()
    mock.emit = MagicMock()
    mock.emit_custom = MagicMock()
    mock.emit_system_event = MagicMock()
    mock.emit_request_budget = MagicMock()
    mock.emit_backoff_applied = MagicMock()
    mock.emit_rate_limit_throttle = MagicMock()
    return mock


@pytest.fixture
def mock_context(cfg, temp_db, mock_telemetry):
    """
    Standard mock context with real config and temp DB.
    """
    ctx = MagicMock()
    ctx.config = cfg
    ctx.persistence = temp_db
    ctx.telemetry = mock_telemetry
    
    # State mock
    ctx.state = MagicMock()
    ctx.state.pattern_pack_loaded = False
    ctx.state.trade_locked = True
    ctx.state.armed = False
    ctx.state.last_scan_ts = None
    
    # Time sync mock
    ctx.time_sync = MagicMock()
    ctx.time_sync.is_healthy = MagicMock(return_value=(True, {"offset_ms": 10}))
    
    # ExchangeInfo mock
    ctx.exchangeinfo_cache = MagicMock()
    ctx.exchangeinfo_cache.get_status = MagicMock(return_value={
        "is_fresh": True, "age_seconds": 1.0, "symbols_count": 100
    })
    ctx.exchangeinfo_cache.get_filters = MagicMock(return_value={
        "tickSize": 0.01, "stepSize": 0.001, "minQty": 0.001, "maxQty": 1000.0
    })
    
    # Risk mock
    ctx.portfolio_risk = MagicMock()
    ctx.portfolio_risk.get_risk_status = MagicMock(return_value={
        "today_pnl": 0.0, "daily_loss_limit": 100.0, "entry_halted": False
    })
    
    return ctx
