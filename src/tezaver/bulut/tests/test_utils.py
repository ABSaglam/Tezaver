"""
Tezaver Bulut - Test Utilities
"""
from fastapi.testclient import TestClient

def make_test_client(app, **kwargs) -> TestClient:
    """
    Create a standardized TestClient with "localhost" or "127.0.0.1" as base_url
    to satisfy TrustedHostMiddleware in tests.
    """
    # Force base_url to localhost if not provided
    if "base_url" not in kwargs:
        kwargs["base_url"] = "http://localhost"
    
    return TestClient(app, **kwargs)
