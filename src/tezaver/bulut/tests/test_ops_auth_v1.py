# Tezaver Bulut - Ops Auth Tests
"""
Tests for Ops Auth Gate Middleware.
"""
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.ops_auth import check_ops_auth
from tezaver.bulut.app_backend import app, ops_auth_middleware

# Mock config
@pytest.fixture
def mock_config():
    cfg = BulutConfig()
    object.__setattr__(cfg, "ops_auth_enabled", True)
    object.__setattr__(cfg, "ops_auth_token_env", "SECRET_123")
    object.__setattr__(cfg, "ops_auth_readonly_allow", True)
    # We patch get_config separately or use dependency override if possible
    # But logic is in core/ops_auth which takes config arg.
    return cfg

def test_check_ops_auth_logic(mock_config):
    """Test middleware logic function directly."""
    import asyncio
    
    # 1. GET (Read-Only Allow)
    req = MagicMock(spec=Request)
    req.method = "GET"
    req.headers = {}
    
    # Should pass (return None)
    try:
        asyncio.run(check_ops_auth(req, mock_config))
    except Exception as e:
        pytest.fail(f"GET failed: {e}")

    # 2. POST (Mutation) - No Token -> Fail
    req.method = "POST"
    with pytest.raises(Exception) as exc:
         asyncio.run(check_ops_auth(req, mock_config))
    assert "401" in str(exc.value.status_code)

    # 3. POST - With Token -> Pass
    req.headers = {"X-TEZAVER-OPS-TOKEN": "SECRET_123"}
    try:
        asyncio.run(check_ops_auth(req, mock_config))
    except Exception as e:
        pytest.fail(f"POST with token failed: {e}")

    # 4. Read-Only Deny Mode
    object.__setattr__(mock_config, "ops_auth_readonly_allow", False)
    req.method = "GET"
    req.headers = {}
    with pytest.raises(Exception) as exc:
         asyncio.run(check_ops_auth(req, mock_config))
    assert "401" in str(exc.value.status_code)

def test_app_middleware_integration(tmp_path):
    """Test integration with TestClient (Mock Config via env var)."""
    import os
    from unittest.mock import patch

    # Safety: Use a fresh DB file for this test
    db_path = tmp_path / "test_tezaver_ops.db"
    
    # Set env vars for Config
    env_patch = {
        "TEZAVER_OPS_TOKEN": "TEST_TOKEN",
        "OPS_AUTH_ENABLED": "true",
        "OPS_AUTH_READONLY_ALLOW": "true",
        "SQLITE_PATH": str(db_path),
        # Disable heavy startup checks if possible or let them run on empty DB
        "STARTUP_SELFTEST_ENABLED": "false", 
        "PROOF_LADDER_AUTO_EVALUATE_ENABLED": "false"
    }
    
    with patch.dict(os.environ, env_patch):
        # Must reload config to pick up env vars because it's cached
        from tezaver.bulut.core.config import reload_config
        reload_config()
        
        # TestClient triggers lifespan
        with TestClient(app) as client:
            # 1. Health (Public)
            resp = client.get("/health")
            assert resp.status_code == 200
            
            # 2. Ops Ping (Mutation) - No Token -> 401
            resp = client.post("/ops/ping")
            assert resp.status_code == 401
            assert "Read-only mode" in resp.json()["detail"]
            
            # 3. Ops Ping - With Token -> 200
            resp = client.post("/ops/ping", headers={"X-TEZAVER-OPS-TOKEN": "TEST_TOKEN"})
            assert resp.status_code == 200
            assert resp.json()["ok"] is True
