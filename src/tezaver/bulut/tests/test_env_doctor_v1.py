import pytest
import os
import tempfile
import sqlite3
from unittest.mock import MagicMock, patch
from pathlib import Path

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.env_doctor import EnvDoctor
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry
from tezaver.bulut.core.context import BulutContext

@pytest.fixture
def base_config(tmp_path):
    return BulutConfig(
        sqlite_path=str(tmp_path / "test.db"),
        startup_selftest_enabled=True,
        startup_fail_fast=False
    )

@pytest.fixture
def telemetry():
    return MagicMock(spec=NdjsonTelemetry)

def test_env_doctor_check_success(base_config, telemetry):
    # Create config with execution disabled
    config = BulutConfig(
        sqlite_path=base_config.sqlite_path,
        execution_enabled=False,
        startup_selftest_enabled=True
    )
    doctor = EnvDoctor(config, telemetry)
    
    # Mock context
    ctx = MagicMock()
    ctx.config = config
    
    report = doctor.run_checks(ctx)
    assert report["status"] in ["OK", "FAIL"] 
    assert "python" in report["checks"]
    assert "dependencies" in report["checks"]
    assert "sqlite" in report["checks"]

# ... previous tests ...

def test_startup_degraded_logic(base_config):
    # Context init takes (config=None)
    ctx = BulutContext(base_config)
    
    # Needs pattern pack loaded to avoid that lock first?
    # Context defaults state fresh.
    ctx.state.pattern_pack_loaded = True 
    
    # Normally OK (if pattern pack loaded)
    # But check_trade_lock logic: 
    # Rule 0: Startup Self-Test (checked first)
    # Rule 1: Pattern Pack (checked second)
    # So if we set degraded=True, it should fail regardless of pattern pack.
    
    # Let's ensure other rules don't interfere.
    # Pattern pack loaded=True is enough for Rule 1.
    
    # Default state is degraded=False
    locked, reason = ctx.check_trade_lock()
    # It might be locked due to other reasons if defaults trigger them?
    # max_open_positions defaults 3 (from config). count is 0.
    # notional defaults 500. current 0.
    # So it should be unlocked if pattern pack is loaded.
    assert locked is False
    
    # Set degraded
    ctx.state.startup_degraded = True
    locked, reason = ctx.check_trade_lock()
    assert locked is True
    assert reason == "STARTUP_SELFTEST_FAIL"

def test_sqlite_write_check(telemetry, tmp_path):
    config = BulutConfig(
        sqlite_path=str(tmp_path / "writable.db"),
        startup_selftest_enabled=True
    )
    doctor = EnvDoctor(config, telemetry)
    
    report = doctor.run_checks()
    assert report["checks"]["sqlite"]["status"] == "OK"
    assert report["checks"]["sqlite"]["writable"] is True

def test_sqlite_readonly_check(telemetry, tmp_path):
    # Create DB file and make it read-only
    db_path = tmp_path / "readonly.db"
    db_path.touch()
    os.chmod(db_path, 0o400) # Read only
    
    config = BulutConfig(
        sqlite_path=str(db_path),
        startup_selftest_enabled=True
    )
    doctor = EnvDoctor(config, telemetry)
    
    report = doctor.run_checks()
    # It might FAIL to connect or FAIL to create table
    assert report["checks"]["sqlite"]["status"] == "FAIL"
    assert report["status"] == "FAIL"



