import pytest
import json
import os
from pathlib import Path
from tezaver.matrix.ops.safety_sweep import run_safety_sweep
from tezaver.matrix.ops.safety_certificate import write_safety_certificate

def test_safety_sweep_detects_red(tmp_path, monkeypatch):
    # Create a mock registry that has a RED protocol
    reg_yaml = tmp_path / "src" / "tezaver" / "matrix" / "protocols" / "safety_protocol_registry.yaml"
    reg_yaml.parent.mkdir(parents=True)
    
    # Create test files so project root is correct
    test_file = tmp_path / "tests" / "dummy_test.py"
    test_file.parent.mkdir()
    test_file.touch()
    
    reg_content = {
        "version": "v1",
        "cloud_locked": False,
        "protocols": [
            {
                "mx": "MX-RED",
                "name": "Red Protocol",
                "active_in": ["WAR"],
                "status": {"WAR": "RED", "LIVE": "GREEN", "SNIPER": "GREEN"},
                "evidence": {"tests": ["tests/dummy_test.py"]}
            },
            {
                "mx": "MX-GREEN",
                "name": "Green Protocol",
                "active_in": ["WAR"],
                "status": {"WAR": "GREEN", "LIVE": "GREEN", "SNIPER": "GREEN"},
                "evidence": {"tests": ["tests/dummy_test.py"]}
            }
        ]
    }
    import yaml
    with open(reg_yaml, "w") as f:
        yaml.dump(reg_content, f)
    
    # Patch SafetyProtocolRegistry to use our mock
    from tezaver.matrix.protocols.safety_registry import SafetyProtocolRegistry
    original_init = SafetyProtocolRegistry.__init__
    
    def mock_init(self, path=None):
        original_init(self, str(reg_yaml))
    
    monkeypatch.setattr(SafetyProtocolRegistry, "__init__", mock_init)
    
    # Run sweep
    run_dir = tmp_path / "run_123"
    run_dir.mkdir()
    
    result = run_safety_sweep(str(run_dir), "WAR")
    
    assert result["verdict"] == "FAIL"
    assert result["counts"]["RED"] == 1
    assert len(result["blockers"]) == 1
    assert result["blockers"][0]["mx"] == "MX-RED"

def test_safety_certificate_writes_files(tmp_path):
    run_dir = tmp_path / "run_456"
    run_dir.mkdir()
    
    sweep_results = {
        "verdict": "PASS",
        "active_stage": "WAR",
        "counts": {"GREEN": 10, "YELLOW": 0, "RED": 0, "GRAY": 0, "LOCKED": 0},
        "blockers": [],
        "warnings": [],
        "protocols": []
    }
    
    json_path = write_safety_certificate(str(run_dir), sweep_results)
    
    assert os.path.exists(json_path)
    assert os.path.exists(run_dir / "reports" / "safety_certificate_v1.md")
    
    with open(json_path) as f:
        cert = json.load(f)
    
    assert cert["version"] == "safety_certificate_v1"
    assert cert["results"]["verdict"] == "PASS"
