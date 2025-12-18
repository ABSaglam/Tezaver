import pytest
from unittest.mock import MagicMock
from tezaver.bulut.services.config_snapshot import ConfigSnapshotService
from tezaver.bulut.services.drift_guard import DriftGuard
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import BulutContext

def test_config_redaction():
    svc = ConfigSnapshotService()
    
    # Mock Config
    # Using simple dict for flexible mocking
    mock_cfg = {
        "binance_api_key": "raw_key",
        "binance_api_secret": "raw_secret",
        "safe_value": "ok",
        "arm_token": "token123"
    }
    
    ctx = MagicMock()
    ctx.config = mock_cfg
    
    snap = svc.snapshot_config(ctx)
    
    assert snap["binance_api_key"] == "***REDACTED***"
    assert snap["binance_api_secret"] == "***REDACTED***"
    assert snap["arm_token"] == "***REDACTED***"
    assert snap["safe_value"] == "ok"
    
    # Check Hashing Determinism
    h1 = svc.hash_config(snap)
    h2 = svc.hash_config(snap)
    assert h1 == h2

# Helper for mocking config object that behaves like dict + attributes
class MockConfigObj:
    def __init__(self, data):
        self._data = data
        self.mode = "TEST"
    def __iter__(self):
        return iter(self._data.items())
    # dict() constructor behavior on objects can be tricky.
    # ConfigSnapshotService uses dict(cfg) if not dataclass.
    # dict(obj) tries keys() or __iter__.
    def keys(self): return self._data.keys()
    def __getitem__(self, k): return self._data[k]

def test_drift_detection_flow():
    # Setup
    svc = ConfigSnapshotService()
    
    mock_conf = MockConfigObj({"val": "A"})
    
    ctx = MagicMock()
    ctx.config = mock_conf
    ctx.config_snapshot = svc
    ctx.persistence = MagicMock()
    ctx.telemetry = MagicMock()
    
    guard = DriftGuard(ctx)
    
    # 1. First Run (Empty DB)
    ctx.persistence.get_latest_config_snapshot.return_value = None
    
    res = guard.check_and_record("STARTUP")
    
    assert res["drift"] is False
    ctx.persistence.insert_config_snapshot.assert_called_once()
    
    # 2. Second Run (Stable)
    # Mock DB return matching hash
    h = res["new_hash"]
    ctx.persistence.get_latest_config_snapshot.return_value = {"hash": h}
    ctx.persistence.insert_config_snapshot.reset_mock()
    
    res2 = guard.check_and_record("CHECKLIST")
    assert res2["drift"] is False
    assert res2["new_hash"] == h
    ctx.persistence.insert_config_snapshot.assert_not_called()
    
    # 3. Third Run (Drift)
    # Change config
    mock_conf._data = {"val": "B"}
    
    ctx.persistence.get_latest_config_snapshot.return_value = {"hash": h} # Old hash in DB
    
    res3 = guard.check_and_record("CHECKLIST")
    assert res3["drift"] is True
    assert res3["new_hash"] != h
    # It should record because drift=True
    ctx.persistence.insert_config_snapshot.assert_called_once()
    assert ctx.telemetry.emit.call_count >= 2 # One for drift, one for save
