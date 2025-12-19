# Tezaver Bulut - Ops Tests
"""
Tests for ops services (status, alerts, incident bundles).
"""
import pytest
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.status_service import StatusService
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.incident_bundle import IncidentBundleService
from tezaver.bulut.schemas.system_status_v1 import SystemStatusV1


def test_status_service_shape(cfg, mock_context):
    """Test SystemStatusV1 generation."""
    svc = StatusService(cfg)
    status = svc.get_status(mock_context)
    
    assert isinstance(status, SystemStatusV1)
    assert status.time_sync.healthy is True
    assert status.time_sync.offset_ms == 10
    assert status.risk.entry_halted is False


def test_alert_persistence(temp_db):
    """Test alert insertion and retrieval using conftest temp_db fixture."""
    temp_db.insert_alert("ERROR", "TEST_CODE", "Test Message", {"foo": "bar"})
    
    alerts = temp_db.get_latest_alerts()
    assert len(alerts) >= 1
    assert alerts[0]["level"] == "ERROR"
    assert alerts[0]["code"] == "TEST_CODE"


def test_incident_bundle_export(tmp_path, cfg):
    """Test zip generation with proper mocks."""
    export_dir = tmp_path / "exports"
    svc = IncidentBundleService(str(export_dir))
    
    # Create mock context with required attributes
    ctx = MagicMock()
    ctx.config = cfg  # Real config (has to_dict)
    
    # Status service mock
    status_svc = MagicMock()
    mock_status = MagicMock()
    mock_status.to_dict.return_value = {"ts": "2024-01-01T00:00:00Z", "daemon": {}}
    status_svc.get_status.return_value = mock_status
    ctx.status_service = status_svc
    
    # Telemetry mock
    telemetry_path = tmp_path / "telemetry.ndjson"
    telemetry_path.touch()
    ctx.telemetry = MagicMock()
    ctx.telemetry._path = telemetry_path
    
    # Persistence mock
    db_path = tmp_path / "bulut.db"
    db_path.touch()
    ctx.persistence = MagicMock()
    ctx.persistence._db_path = str(db_path)
    
    zip_path = svc.create_bundle(ctx, "test_reason")
    
    assert os.path.exists(zip_path)
    assert zip_path.endswith(".zip")
    assert "test_reason" in zip_path
