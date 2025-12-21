import pytest
import os
import yaml
from tezaver.matrix.protocols.safety_registry import SafetyProtocolRegistry, SafetyStatus

def test_safety_registry_loads_yaml(tmp_path):
    # Create a dummy registry YAML
    reg_path = tmp_path / "safety_test.yaml"
    data = {
        "version": "test_v1",
        "cloud_locked": True,
        "protocols": [
            {
                "mx": "MX-TEST",
                "name": "Test Protocol",
                "active_in": ["LIVE"],
                "status": {"LIVE": "GREEN"}
            }
        ]
    }
    with open(reg_path, "w") as f:
        yaml.dump(data, f)
    
    registry = SafetyProtocolRegistry(path=str(reg_path))
    assert registry.version == "test_v1"
    assert registry.cloud_locked is True
    assert len(registry.protocols) == 1
    assert registry.protocols[0]["mx"] == "MX-TEST"

def test_compute_overall_status(tmp_path):
    reg_path = tmp_path / "status_test.yaml"
    data = {
        "protocols": [
            {
                "mx": "MX-RED",
                "active_in": ["SNIPER", "LIVE"],
                "status": {"SNIPER": "RED", "LIVE": "GREEN"}
            },
            {
                "mx": "MX-YELLOW",
                "active_in": ["WAR"],
                "status": {"WAR": "YELLOW"}
            }
        ]
    }
    with open(reg_path, "w") as f:
        yaml.dump(data, f)
    
    registry = SafetyProtocolRegistry(path=str(reg_path))
    
    # Specific stage status
    assert registry.compute_overall_status("MX-RED", stage="SNIPER") == SafetyStatus.RED
    assert registry.compute_overall_status("MX-RED", stage="LIVE") == SafetyStatus.GREEN
    
    # Overall (worst of active)
    assert registry.get_overall_for_active("MX-RED") == SafetyStatus.RED
    assert registry.get_overall_for_active("MX-YELLOW") == SafetyStatus.YELLOW

def test_registry_rows_content(tmp_path):
    reg_path = tmp_path / "rows_test.yaml"
    data = {
        "protocols": [
            {
                "mx": "MX-1",
                "name": "P1",
                "purpose": "Purp1",
                "active_in": ["LIVE"],
                "status": {"LIVE": "GREEN"},
                "evidence": {"tests": ["t1"]}
            }
        ]
    }
    with open(reg_path, "w") as f:
        yaml.dump(data, f)
    
    registry = SafetyProtocolRegistry(path=str(reg_path))
    rows = registry.get_ui_rows()
    
    assert len(rows) == 1
    row = rows[0]
    assert row["MX"] == "MX-1"
    assert "GREEN" in row["LIVE"]
    assert "🧪 1" in row["Evidence"]
