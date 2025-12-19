# Tezaver Bulut - Replay API Tests
import pytest
from starlette.testclient import TestClient
from unittest.mock import MagicMock, patch

from tezaver.bulut.app_backend import app
from tezaver.bulut.core.context import BulutContext
from tezaver.bulut.schemas.replay_v1 import ReplayBundleV1, ReplayResultV1

@pytest.fixture
def app_client():
    # Setup mock context on app state
    mock_ctx = MagicMock(spec=BulutContext)
    
    # AsyncMock for awaited methods
    from unittest.mock import AsyncMock
    mock_ctx.time_sync.refresh = AsyncMock()
    mock_ctx.scheduler.start = AsyncMock()
    mock_ctx.scheduler.stop_all = AsyncMock()
    mock_ctx.task_supervisor.start_all = AsyncMock()
    mock_ctx.task_supervisor.stop_all = AsyncMock()
    mock_ctx.executor.recover_executing_plans = AsyncMock()
    mock_ctx.executor.cleanup = AsyncMock()
    mock_ctx.exchangeinfo_cache.refresh = AsyncMock()

    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = [
        {"bundle_id": "b1", "cycle_ts": "t1", "created_ts": "t2", "notes": "n1", "status": "CREATED"}
    ]
    cursor.fetchone.return_value = {"result_json": '{"status": "MATCH"}'}
    
    # Connect
    mock_ctx.persistence._get_conn.return_value = conn
    
    # Needs to be serializable
    mock_ctx.config.to_dict.return_value = {"mock": "config"}
    mock_ctx.persistence.get_open_position_count.return_value = 0
    mock_ctx.persistence.get_total_notional.return_value = 0.0

    # Startup mocks
    mock_ctx.load_pattern_pack.return_value = True
    mock_ctx.state.pattern_pack_id = "SMOKE_TEST"
    mock_ctx.state.trade_locked = True
    mock_ctx.config.time_sync_enabled = True
    mock_ctx.config.exchangeinfo_refresh_on_start = True
    mock_ctx.config.startup_selftest_enabled = False
    mock_ctx.config.migrations_enabled = False
    mock_ctx.config.user_data_ws_enabled = False
    mock_ctx.config.proof_ladder_auto_evaluate_enabled = False
    mock_ctx.config.allowed_hosts = ["testserver"] 

    # Patch BOOTSTRAP in app_backend!
    with patch("tezaver.bulut.app_backend.bootstrap_context", return_value=mock_ctx):
        # Disable Ops Auth via Env
        import os
        with patch.dict("os.environ", {"OPS_AUTH_ENABLED": "false", "ALLOWED_HOSTS": "*"}):
            from tezaver.bulut.core.config import reload_config
            reload_config()
        
            # Add base_url="http://localhost" to bypass TrustedHostMiddleware check
            with TestClient(app, base_url="http://localhost") as client:
                app.state.context = mock_ctx
                yield client


@pytest.fixture
def mock_collector():
    with patch("tezaver.bulut.api.routes_replay.ReplayCollectorService") as mock:
        yield mock

@pytest.fixture
def mock_engine():
    with patch("tezaver.bulut.api.routes_replay.ReplayEngine") as mock:
        yield mock

def test_create_bundle(app_client, mock_collector):
    # Mock return
    mock_inst = mock_collector.return_value
    mock_inst.create_bundle_from_current_state.return_value = MagicMock(bundle_id="new_bundle")
    
    resp = app_client.post("/replay/bundle/create", json={"notes": "test"})
    assert resp.status_code == 200
    assert resp.json()["bundle_id"] == "new_bundle"

def test_list_bundles(app_client):
    resp = app_client.get("/replay/bundles/latest")
    assert resp.status_code == 200, f"Failed: {resp.text}"
    data = resp.json()
    assert len(data) == 1
    assert data[0]["bundle_id"] == "b1"

def test_run_replay(app_client, mock_collector, mock_engine):
    # Setup
    bundle_mock = MagicMock(spec=ReplayBundleV1)
    bundle_mock.bundle_id = "b1"
    mock_collector.return_value.get_bundle.return_value = bundle_mock
    
    res_mock = ReplayResultV1(
        run_id="run1", bundle_id="b1", status="MATCH", executed_ts="t1", drift_details={}, logs=[]
    )
    mock_engine.return_value.run_replay.return_value = res_mock
    
    resp = app_client.post("/replay/run", json={"bundle_id": "b1"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "MATCH"

def test_get_result(app_client):
    resp = app_client.get("/replay/result/b1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "MATCH"
