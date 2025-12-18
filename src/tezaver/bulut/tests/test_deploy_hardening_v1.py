"""
Deploy Hardening v1 Tests
Verifies: TrustedHost, SecureHeaders, RateLimit middlewares
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from unittest.mock import patch
import os

from tezaver.bulut.core.config import reload_config, get_config
from tezaver.bulut.core.middleware_security import SecureHeadersMiddleware, BasicRateLimitMiddleware


def create_test_app(cfg):
    """Create a fresh app instance with middlewares for testing."""
    app = FastAPI()
    
    @app.get("/health")
    def health():
        return {"status": "ok"}
    
    @app.get("/ops/secret")
    def ops_secret():
        return {"secret": True}
    
    @app.post("/ops/ping")
    def ops_ping():
        return {"ok": True}
    
    # Add middlewares in correct order (last = outermost)
    # 1. Rate Limit (innermost)
    app.add_middleware(BasicRateLimitMiddleware, config=cfg)
    
    # 2. Trusted Host
    if cfg.allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=cfg.allowed_hosts)
    
    # 3. Secure Headers (outermost)
    app.add_middleware(SecureHeadersMiddleware, config=cfg)
    
    return app


def test_trusted_host_rejects_unknown(tmp_path):
    """TrustedHostMiddleware should reject unknown hosts with 400."""
    db_path = tmp_path / "test.db"
    
    env = {
        "DEPLOY_ENV": "PROD",
        "ALLOWED_HOSTS": "localhost,127.0.0.1",
        "SECURE_HEADERS_ENABLED": "true",
        "BASIC_RATE_LIMIT_ENABLED": "false",  # Disable to isolate test
        "SQLITE_PATH": str(db_path),
    }
    
    with patch.dict(os.environ, env, clear=False):
        reload_config()
        cfg = get_config()
        app = create_test_app(cfg)
        
        with TestClient(app, raise_server_exceptions=False) as client:
            # Unknown host should fail
            resp = client.get("/health", headers={"Host": "malicious.com"})
            assert resp.status_code == 400
            
            # Secure headers should still be present on 400
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"


def test_trusted_host_allows_valid(tmp_path):
    """TrustedHostMiddleware should allow valid hosts."""
    db_path = tmp_path / "test.db"
    
    env = {
        "DEPLOY_ENV": "PROD",
        "ALLOWED_HOSTS": "localhost,127.0.0.1",
        "SECURE_HEADERS_ENABLED": "true",
        "BASIC_RATE_LIMIT_ENABLED": "false",
        "SQLITE_PATH": str(db_path),
    }
    
    with patch.dict(os.environ, env, clear=False):
        reload_config()
        cfg = get_config()
        app = create_test_app(cfg)
        
        with TestClient(app) as client:
            resp = client.get("/health", headers={"Host": "localhost"})
            assert resp.status_code == 200


def test_secure_headers_present_on_200(tmp_path):
    """Secure headers should be present on successful responses."""
    db_path = tmp_path / "test.db"
    
    env = {
        "DEPLOY_ENV": "PROD",
        "ALLOWED_HOSTS": "localhost",
        "SECURE_HEADERS_ENABLED": "true",
        "BASIC_RATE_LIMIT_ENABLED": "false",
        "SQLITE_PATH": str(db_path),
    }
    
    with patch.dict(os.environ, env, clear=False):
        reload_config()
        cfg = get_config()
        app = create_test_app(cfg)
        
        with TestClient(app) as client:
            resp = client.get("/health", headers={"Host": "localhost"})
            assert resp.status_code == 200
            
            # Check security headers
            assert resp.headers.get("X-Content-Type-Options") == "nosniff"
            assert resp.headers.get("X-Frame-Options") == "DENY"
            assert "strict-origin" in resp.headers.get("Referrer-Policy", "")


def test_secure_headers_cache_control_on_ops(tmp_path):
    """Ops endpoints should have Cache-Control: no-store."""
    db_path = tmp_path / "test.db"
    
    env = {
        "DEPLOY_ENV": "PROD",
        "ALLOWED_HOSTS": "localhost",
        "SECURE_HEADERS_ENABLED": "true",
        "BASIC_RATE_LIMIT_ENABLED": "false",
        "SQLITE_PATH": str(db_path),
    }
    
    with patch.dict(os.environ, env, clear=False):
        reload_config()
        cfg = get_config()
        app = create_test_app(cfg)
        
        with TestClient(app) as client:
            resp = client.get("/ops/secret", headers={"Host": "localhost"})
            assert resp.status_code == 200
            assert "no-store" in resp.headers.get("Cache-Control", "")


def test_rate_limit_triggers_429(tmp_path):
    """Rate limiter should trigger 429 on burst."""
    db_path = tmp_path / "test.db"
    
    env = {
        "DEPLOY_ENV": "PROD",
        "ALLOWED_HOSTS": "localhost",
        "SECURE_HEADERS_ENABLED": "true",
        "BASIC_RATE_LIMIT_ENABLED": "true",
        "BASIC_RATE_LIMIT_RPS": "1",
        "BASIC_RATE_LIMIT_BURST": "2",  # Only 2 requests allowed
        "SQLITE_PATH": str(db_path),
    }
    
    with patch.dict(os.environ, env, clear=False):
        reload_config()
        cfg = get_config()
        app = create_test_app(cfg)
        
        with TestClient(app) as client:
            # Burst requests
            responses = []
            for _ in range(10):
                resp = client.post("/ops/ping", headers={"Host": "localhost"})
                responses.append(resp.status_code)
            
            # At least one should be 429
            assert 429 in responses, f"Expected 429 in {responses}"
            
            # Find a 429 response and check headers
            for _ in range(5):
                resp = client.post("/ops/ping", headers={"Host": "localhost"})
                if resp.status_code == 429:
                    # Secure headers should be present even on 429
                    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
                    break
