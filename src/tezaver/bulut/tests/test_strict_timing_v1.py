# Tezaver Bulut - Strict Timing V1 Tests
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime
from tezaver.bulut.core.strict_timing_service import StrictTimingService
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.schemas.cycle_timeline_v1 import CycleTimelineV1

@pytest.fixture
def mock_persistence():
    p = MagicMock()
    p.check_dedupe_run.return_value = None
    return p

@pytest.fixture
def mock_config():
    # Use standard dataclass, override fields via mock or subclass if needed, 
    # but BulutConfig is frozen.
    # We can mock the object itself.
    cfg = MagicMock(spec=BulutConfig)
    cfg.strict_timing_enabled = True
    cfg.max_drift_ms = 5000
    cfg.mode = "TESTNET"
    return cfg

@pytest.fixture
def service(mock_persistence, mock_config):
    telemetry = MagicMock()
    return StrictTimingService(mock_persistence, mock_config, telemetry)

def test_on_cycle_attempt_allow_normal(service):
    close_ts = datetime.fromisoformat("2025-01-01T12:00:00+00:00")
    now_ts = datetime.fromisoformat("2025-01-01T12:00:01+00:00") # 1s drift
    
    res = service.on_cycle_attempt(close_ts, now_ts)
    
    assert res["status"] == "ALLOW"
    assert res["drift_ms"] == 1000
    service.db.check_dedupe_run.assert_called_once()

def test_on_cycle_attempt_dedupe_block(service):
    close_ts = datetime.fromisoformat("2025-01-01T12:00:00+00:00")
    now_ts = datetime.fromisoformat("2025-01-01T12:00:01+00:00")
    
    # Mock DB saying it exists
    service.db.check_dedupe_run.return_value = {
        "bar_close_ts": close_ts.isoformat(),
        "run_ts": "2025-01-01T12:00:01+00:00",
        "last_cycle_id": 123
    }
    
    res = service.on_cycle_attempt(close_ts, now_ts)
    
    assert res["status"] == "BLOCK"
    assert res["reason"] == "DEDUPED"
    from unittest.mock import ANY
    service.telemetry.emit.assert_called_with("STRICT_TIMING_DEDUPED", ANY)

def test_on_cycle_attempt_drift_alert_non_mainnet(service):
    close_ts = datetime.fromisoformat("2025-01-01T12:00:00+00:00")
    now_ts = datetime.fromisoformat("2025-01-01T12:00:10+00:00") # 10s drift (limit 5s)
    
    service.config.mode = "TESTNET"
    
    res = service.on_cycle_attempt(close_ts, now_ts)
    
    assert res["status"] == "ALLOW" # In TESTNET we just alert but allow
    assert res["drift_ms"] == 10000
    from unittest.mock import ANY
    service.telemetry.emit.assert_called_with("STRICT_TIMING_DRIFT_ALERT", ANY)

def test_on_cycle_attempt_drift_block_mainnet(service):
    close_ts = datetime.fromisoformat("2025-01-01T12:00:00+00:00")
    now_ts = datetime.fromisoformat("2025-01-01T12:00:10+00:00") # 10s drift
    
    service.config.mode = "MAINNET"
    
    res = service.on_cycle_attempt(close_ts, now_ts)
    
    assert res["status"] == "BLOCK"
    assert res["reason"] == "DRIFT_VIOLATION"
    from unittest.mock import ANY
    service.telemetry.emit.assert_called_with("STRICT_TIMING_DRIFT_ALERT", ANY)

def test_record_success(service):
    close_ts = datetime.fromisoformat("2025-01-01T12:00:00+00:00")
    cycle_id = 100
    
    service.record_success(close_ts, cycle_id)
    
    service.db.register_dedupe_run.assert_called_once()
    args = service.db.register_dedupe_run.call_args[0]
    assert args[0] == close_ts.isoformat()
    assert args[1] == 100
    # run_ts and ran_at_ms are generated inside
