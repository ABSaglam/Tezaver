# Tezaver Bulut - Strict Timing API Tests
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch

from tezaver.bulut.app_backend import app, lifespan
from tezaver.bulut.core.context import BulutContext

@pytest.fixture
def smoke_client():
    """Client with mocked context."""
    # Mock lifespan
    with patch("tezaver.bulut.app_backend.bootstrap_context") as mock_boot:
        ctx = MagicMock(spec=BulutContext)
        mock_boot.return_value = ctx
        
        # Mock Config
        ctx.config.strict_timing_enabled = True
        ctx.config.max_drift_ms = 5000
        ctx.config.mode = "TESTNET"
        
        # Mock Lifespan dependencies
        ctx.time_sync.refresh = AsyncMock()
        ctx.scheduler.start = AsyncMock()
        ctx.scheduler.stop = AsyncMock()
        ctx.task_supervisor.start_all = AsyncMock()
        ctx.task_supervisor.stop_all = AsyncMock()
        # Initial Reconciliation
        ctx.reconciliation_service.reconcile = AsyncMock(return_value={"status": "OK"})
        
        # ExchangeInfo Cache
        ctx.exchangeinfo_cache.refresh = AsyncMock()
        
        # Executor
        ctx.executor.recover_executing_plans = AsyncMock()
        
        # Mock Persistence (for status query)
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = ("2025-01-01T12:00:00+00:00", 1, 1000, "2025-01-01T12:00:01+00:00")
        cursor.fetchall.return_value = [(1, "2025-01-01T12:00:00+00:00", "{\"drift_ms\": 50}")]
        
        ctx.persistence._get_conn.return_value = conn
        conn.cursor.return_value = cursor
        
        # Setup app state
        with TestClient(app, base_url="http://localhost") as client:
            app.state.context = ctx # Explicitly attach
            yield client

def test_get_status(smoke_client):
    resp = smoke_client.get("/strict_timing/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["enabled"] is True
    assert data["last_run"]["bar_close_ts"] == "2025-01-01T12:00:00+00:00"

def test_get_timeline(smoke_client):
    resp = smoke_client.get("/strict_timing/timeline")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["drift_ms"] == 50
