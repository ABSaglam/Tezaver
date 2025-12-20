import os
import json
import pytest
from tezaver.matrix.core.ops_health import build_health_snapshot

def test_ops_health_overall_rules(tmp_path):
    home = str(tmp_path)
    
    # Setup Dirs
    for d in ["ops", "cloud_runtime", "alerts/active"]:
        os.makedirs(tmp_path / d, exist_ok=True)
        
    # Case 4: Green (Minimal)
    # No alerts, no pause, no real mode issues
    # But secrets? If load_secrets fails it might be false.
    # Secrets loader defaults to checked from env or file.
    # If secrets missing, "secrets_present" is false.
    # If mode is not real, it's ok.
    # Default broker mode is "UNKNOWN", signals "UNKNOWN".
    # Let's write broker config PAPER.
    with open(tmp_path / "cloud_runtime" / "broker_config.json", "w") as f:
        json.dump({"mode": "PAPER"}, f)
        
    s = build_health_snapshot(home)
    assert s["overall"] == "GREEN" or s["overall"] == "YELLOW" # Preflight might fail if report missing?
    # Logic: if preflight missing, preflight_ok=False -> YELLOW.
    # So expected YELLOW unless we mock preflight pass.
    
    os.makedirs(tmp_path / "ops" / "preflight", exist_ok=True)
    with open(tmp_path / "ops" / "preflight" / "latest.json", "w") as f:
        json.dump({"status": "PASS"}, f)
        
    s = build_health_snapshot(home)
    assert s["overall"] == "GREEN"
    
    # Case 1: Paused -> RED
    with open(tmp_path / "cloud_runtime" / "global_risk.json", "w") as f:
        json.dump({"paused": True}, f)
    s = build_health_snapshot(home)
    assert s["overall"] == "RED"
    
    # Reset Paused
    with open(tmp_path / "cloud_runtime" / "global_risk.json", "w") as f:
        json.dump({"paused": False}, f)
        
    # Case 3: Warn Alert -> YELLOW
    with open(tmp_path / "alerts" / "active" / "A1.json", "w") as f:
        json.dump({"level": "WARNING"}, f)
    s = build_health_snapshot(home)
    assert s["overall"] == "YELLOW"
    
    # Case: Critical Alert -> RED
    with open(tmp_path / "alerts" / "active" / "A2.json", "w") as f:
        json.dump({"level": "CRITICAL"}, f)
    s = build_health_snapshot(home)
    assert s["overall"] == "RED"
