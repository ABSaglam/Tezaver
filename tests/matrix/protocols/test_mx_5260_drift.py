import pytest
import json
import os
from pathlib import Path
from tezaver.matrix.protocols.safety_registry import SafetyProtocolRegistry

def test_check_evidence_missing_telemetry(tmp_path):
    # Setup dummy registry yaml
    reg_yaml = tmp_path / "safety_protocol_registry.yaml"
    reg_content = {
        "protocols": [
            {
                "mx": "MX-TEST",
                "name": "Test Protocol",
                "evidence": {
                    "telemetry": ["EXPECTED_EVT"],
                    "artifacts": ["missing.txt"]
                }
            }
        ]
    }
    with open(reg_yaml, "w") as f:
        import yaml
        yaml.dump(reg_content, f)
        
    registry = SafetyProtocolRegistry(str(reg_yaml))
    
    # Non-existent run_dir
    drift = registry.check_evidence("MX-TEST", str(tmp_path / "no_run"))
    assert "EXPECTED_EVT" in drift["telemetry"]
    assert "missing.txt" in drift["artifacts"]
    
    # Run dir exists but telemetry empty
    run_dir = tmp_path / "run_123"
    run_dir.mkdir()
    with open(run_dir / "telemetry.ndjson", "w") as f:
        f.write(json.dumps({"event_type": "OTHER_EVT"}) + "\n")
        
    drift = registry.check_evidence("MX-TEST", str(run_dir))
    assert "EXPECTED_EVT" in drift["telemetry"]
    assert "missing.txt" in drift["artifacts"]

def test_check_evidence_all_ok(tmp_path, monkeypatch):
    # Setup dummy registry yaml
    reg_yaml = tmp_path / "safety_protocol_registry.yaml"
    reg_content = {
        "protocols": [
            {
                "mx": "MX-OK",
                "name": "OK Protocol",
                "evidence": {
                    "telemetry": ["OK_EVT"],
                    "artifacts": ["ok.txt"],
                    "tests": ["tests/dummy_test.py"]
                }
            }
        ]
    }
    with open(reg_yaml, "w") as f:
        import yaml
        yaml.dump(reg_content, f)
        
    registry = SafetyProtocolRegistry(str(reg_yaml))
    
    # Setup project structure
    # The registry logic expects project root to be 4 levels up from reg_yaml if default
    # but here we use a custom path. Let's mock project_root or just create the path it expects.
    # Actually, the logic in check_evidence derives project_root relative to self.path.
    # project_root = tmp_path (root for our tests)
    # We need to simulate the depth.
    depth_dir = tmp_path / "src" / "tezaver" / "matrix" / "protocols"
    depth_dir.mkdir(parents=True)
    real_reg_yaml = depth_dir / "safety_protocol_registry.yaml"
    with open(real_reg_yaml, "w") as f:
        import yaml
        yaml.dump(reg_content, f)
        
    registry = SafetyProtocolRegistry(str(real_reg_yaml))
    
    # Create test file
    test_file = tmp_path / "tests" / "dummy_test.py"
    test_file.parent.mkdir()
    test_file.touch()
    
    # Create run artifacts
    run_dir = tmp_path / "run_ok"
    run_dir.mkdir()
    with open(run_dir / "telemetry.ndjson", "w") as f:
        f.write(json.dumps({"event_type": "OK_EVT"}) + "\n")
    (run_dir / "ok.txt").touch()
    
    drift = registry.check_evidence("MX-OK", str(run_dir))
    assert not any(drift.values())
