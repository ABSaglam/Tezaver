# Tezaver Bulut - Router Wiring Smoke Test
import pytest
from starlette.testclient import TestClient
from unittest.mock import MagicMock, patch

from tezaver.bulut.app_backend import app
from tezaver.bulut.core.context import BulutContext

# FIXTURE: This runs on the REAL app instance from app_backend.py
# We only mock the context to avoid starting full services.

@pytest.fixture
def smoke_client():
    mock_ctx = MagicMock(spec=BulutContext)
    
    # Use AsyncMock for methods awaited in lifespan
    from unittest.mock import AsyncMock
    mock_ctx.time_sync.refresh = AsyncMock()
    mock_ctx.scheduler.start = AsyncMock()
    mock_ctx.scheduler.stop_all = AsyncMock() # if accessed
    mock_ctx.task_supervisor.start_all = AsyncMock()
    mock_ctx.task_supervisor.stop_all = AsyncMock()
    mock_ctx.executor.recover_executing_plans = AsyncMock()
    mock_ctx.executor.cleanup = AsyncMock()
    mock_ctx.exchangeinfo_cache.refresh = AsyncMock()
    
    # Necessary mocks for startup to pass if lifespan runs
    mock_ctx.load_pattern_pack.return_value = True
    mock_ctx.state.pattern_pack_id = "SMOKE_TEST"
    mock_ctx.state.trade_locked = True
    mock_ctx.config.time_sync_enabled = True # Let it run refresh mock
    mock_ctx.config.exchangeinfo_refresh_on_start = True # Let it run refresh mock
    mock_ctx.config.startup_selftest_enabled = False
    mock_ctx.config.migrations_enabled = False
    mock_ctx.config.user_data_ws_enabled = False
    mock_ctx.config.proof_ladder_auto_evaluate_enabled = False
    mock_ctx.config.allowed_hosts = ["testserver"] # Matches TestClient default
    mock_ctx.config.ops_auth_enabled = False # Disable auth for smoke test
    mock_ctx.config.rate_limiter_enabled = False  # Disable rate limiter in tests
    
    # Needs config.to_dict for Replay Logic potentially?
    mock_ctx.config.to_dict.return_value = {}
    
    # Mock persistence for DB queries
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    # Default fetchall for list calls
    cursor.fetchall.return_value = []
    
    # For GET /ops/tests/report
    mock_ctx.config.ndjson_path = "/tmp/fake.ndjson"
    
    mock_ctx.persistence._get_conn.return_value = conn
    
    # Mock Fault Lab Service (since we bypass startup)
    mock_fault_service = MagicMock()
    mock_fault_service.list_profiles.return_value = []
    
    # Patch BOOTSTRAP in app_backend!
    with patch("tezaver.bulut.app_backend.bootstrap_context", return_value=mock_ctx):
        # Patch config reload to ensure OPS_AUTH_ENABLED=False applies
        with patch.dict("os.environ", {"OPS_AUTH_ENABLED": "false", "ALLOWED_HOSTS": "*"}):
             # Force reload config inside the app logic if it reloads?
             # app_backend imports check_ops_auth which calls get_config().
             # We should ensure get_config returns our loose config or we disable check via env.
             
             # Re-init client trigger lifespan
            with TestClient(app, base_url="http://localhost") as client:
                app.state.context = mock_ctx # Force set context on state
                app.state.fault_lab_service = mock_fault_service # Manually attach service
                yield client

def test_fault_lab_wiring(smoke_client):
    """Verify Fault Lab routes are registered and reachable."""
    # /fault/profiles is a likely endpoint (GET)
    # Check routes_fault_lab.py to be sure of path.
    # Assuming list profiles or similar.
    # Actually, P1 spec said `GET /fault/profiles`.
    # Let's try root or known path.
    resp = smoke_client.get("/fault/profiles") 
    assert resp.status_code in [200, 404] 
    # If 404, route might be wrong. If 200, wired.
    # If 403/401, auth blocking.
    
    if resp.status_code == 404:
        # Maybe route is different? 
        # routes_fault_lab.py usually defined router with prefix
        # app included with prefix "/fault"
        # router path "/" -> "/fault/"?
        pytest.fail(f"Fault Lab endpoint not found: {resp.status_code}")

def test_replay_lab_wiring(smoke_client):
    """Verify Replay Lab routes are registered and reachable."""
    # /replay/bundles/latest is defined in routes_replay.py
    # app included with tags=["Replay Lab"] but NO PREFIX in app_backend?
    # Let's check app_backend.py:
    # app.include_router(routes_replay.router, tags=["Replay Lab"]) 
    # -> NO PREFIX provided in include!
    # routes_replay.py: router = APIRouter(prefix="/replay", ...)
    # So path is /replay/bundles/latest.
    
    resp = smoke_client.get("/replay/bundles/latest")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_ops_report_wiring(smoke_client):
    """Verify Ops Reports endpoint."""
    resp = smoke_client.get("/ops/tests/report")
    # Might return 200 or 500 if xml missing, but route reachable?
    # routes_ops: GET /tests/report
    # app_backend: prefix /ops
    # -> /ops/tests/report
    
    if resp.status_code == 404:
         pytest.fail("Ops report endpoint not found")
    
    # 500 is acceptable if logic fails (missing file), but 404 means unwired.
    assert resp.status_code != 404
