# Tezaver Bulut - Fault Lab UI API Tests
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tezaver.bulut.api.routes_fault_lab import router
from tezaver.bulut.core.fault_lab_service import FaultLabService
from tezaver.bulut.core.fault_injector import FaultInjector

# --- Fixtures ---

@pytest.fixture
def mock_service():
    mock_svc = MagicMock(spec=FaultLabService)
    mock_svc.list_profiles.return_value = [
        {"id": "test_p", "name": "Test Profile", "description": "Desc"}
    ]
    mock_svc.activate_profile.return_value = True
    mock_svc.get_active_profile.return_value = "test_p"
    mock_svc.get_runs.return_value = []
    # Injector mock
    mock_svc.injector = MagicMock(spec=FaultInjector)
    return mock_svc

@pytest.fixture
def app_client(mock_service):
    app = FastAPI()
    app.include_router(router)
    
    # Inject mock service into state
    app.state.fault_lab_service = mock_service
    
    return TestClient(app)

# --- Tests ---

def test_list_profiles(app_client):
    resp = app_client.get("/fault/profiles")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["id"] == "test_p"

def test_activate_profile(app_client, mock_service):
    resp = app_client.post("/fault/activate", json={"profile_id": "test_p"})
    assert resp.status_code == 200
    mock_service.activate_profile.assert_called_with("test_p")

def test_activate_profile_not_found(app_client, mock_service):
    mock_service.activate_profile.return_value = False
    resp = app_client.post("/fault/activate", json={"profile_id": "missing"})
    assert resp.status_code == 404

def test_deactivate_profile(app_client, mock_service):
    resp = app_client.post("/fault/deactivate")
    assert resp.status_code == 200
    mock_service.deactivate.assert_called_once()

def test_list_runs(app_client):
    resp = app_client.get("/fault/runs")
    assert resp.status_code == 200
    assert resp.json() == []

def test_get_active(app_client):
    resp = app_client.get("/fault/active")
    assert resp.status_code == 200
    assert resp.json()["active_profile_id"] == "test_p"
