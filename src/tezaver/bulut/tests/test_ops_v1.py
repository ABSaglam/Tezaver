# Tezaver Bulut - Ops Tests
import pytest
import os
import shutil
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.services.status_service import StatusService
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.incident_bundle import IncidentBundleService
from tezaver.bulut.schemas.system_status_v1 import SystemStatusV1

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    p = SqlitePersistence(str(db_path))
    yield p
    p._get_conn().close()

@pytest.fixture
def mock_ctx(tmp_path):
    ctx = MagicMock(spec=BulutContext)
    config = BulutConfig()
    ctx.config = config
    
    # State Mock
    ctx.state = MagicMock()
    ctx.state.last_scan_ts = None # or a string if needed, but None is safe
    # If code calls .isoformat on None it crashes? 
    # StatusService: getattr(state, "last_scan_ts", None).isoformat() if ... else None
    # So if last_scan_ts is None, it returns None.
    
    # TimeSync Mock
    ctx.time_sync = MagicMock()
    ctx.time_sync.is_healthy.return_value = (True, {"offset_ms": 10})
    
    # ExchangeInfo Mock
    ctx.exchangeinfo_cache = MagicMock()
    ctx.exchangeinfo_cache.get_status.return_value = {"is_fresh": True, "age_seconds": 1.0, "symbols_count": 10}
    
    # Risk Mock
    ctx.portfolio_risk = MagicMock()
    ctx.portfolio_risk.get_risk_status.return_value = {"today_pnl": 0.0, "daily_loss_limit": 100.0, "entry_halted": False}
    
    return ctx

def test_status_service_shape(mock_ctx):
    """Test SystemStatusV1 generation."""
    svc = StatusService(mock_ctx.config)
    status = svc.get_status(mock_ctx)
    
    assert isinstance(status, SystemStatusV1)
    assert status.time_sync.healthy is True
    assert status.time_sync.offset_ms == 10
    assert status.risk.entry_halted is False
    assert status.execution.enabled == mock_ctx.config.execution_enabled

def test_alert_persistence(temp_db):
    """Test alert insertion and retrieval."""
    temp_db.insert_alert("ERROR", "TEST_CODE", "Test Message", {"foo": "bar"})
    
    alerts = temp_db.get_latest_alerts()
    assert len(alerts) == 1
    assert alerts[0]["level"] == "ERROR"
    assert alerts[0]["code"] == "TEST_CODE"
    assert alerts[0]["details"] == {"foo": "bar"}

def test_incident_bundle_export(tmp_path, mock_ctx):
    """Test zip generation."""
    export_dir = tmp_path / "exports"
    svc = IncidentBundleService(str(export_dir))
    
    # Mock status service on ctx
    mock_ctx.status_service = StatusService(mock_ctx.config)
    mock_ctx.telemetry = MagicMock()
    mock_ctx.telemetry._path = tmp_path / "telemetry.ndjson"
    mock_ctx.telemetry._path.touch()
    
    mock_ctx.persistence = MagicMock()
    mock_ctx.persistence._db_path = tmp_path / "bulut.db"
    mock_ctx.persistence._db_path.touch()
    
    zip_path = svc.create_bundle(mock_ctx, "test_reason")
    
    assert os.path.exists(zip_path)
    assert zip_path.endswith(".zip")
    assert "test_reason" in zip_path
    
    # Verify contents
    import zipfile
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        assert "config.json" in names
        assert "status.json" in names
        # paths in zip are relative
        assert any("metadata.txt" in n for n in names)
