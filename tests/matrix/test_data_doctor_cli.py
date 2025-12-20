import pytest
import subprocess
import sys
import json
import os

def test_data_doctor_cli_ok(tmp_path):
    bars_file = tmp_path / "bars.json"
    bars_data = [
        {"ts": 0, "open": 1, "high": 2, "low": 0.5, "close": 1, "is_closed": True},
        {"ts": 900, "open": 1, "high": 2, "low": 0.5, "close": 1, "is_closed": True}
    ]
    with open(bars_file, "w") as f:
        json.dump(bars_data, f)
        
    home = tmp_path / "home"
    
    cmd = [
        sys.executable, "-m", "tezaver.matrix.apps.data_doctor",
        "--path", str(bars_file),
        "--timeframe", "15m",
        "--home", str(home)
    ]
    
    env = os.environ.copy()
    if 'PYTHONPATH' not in env:
        env['PYTHONPATH'] = os.getcwd() + "/src"

    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode == 0
    assert "[OK]" in res.stdout
    
    # Check report
    latest = home / "data_reports" / "latest.json"
    assert latest.exists()
    
def test_data_doctor_cli_fail(tmp_path):
    bars_file = tmp_path / "bars.json"
    # Duplicate timestamps
    bars_data = [
        {"ts": 0, "open": 1, "high": 2, "low": 0.5, "close": 1, "is_closed": True},
        {"ts": 0, "open": 1, "high": 2, "low": 0.5, "close": 1, "is_closed": True}
    ]
    with open(bars_file, "w") as f:
        json.dump(bars_data, f)
        
    home = tmp_path / "home"
    
    cmd = [
        sys.executable, "-m", "tezaver.matrix.apps.data_doctor",
        "--path", str(bars_file),
        "--timeframe", "15m", # 900s
        "--home", str(home)
    ]
    
    env = os.environ.copy()
    if 'PYTHONPATH' not in env:
        env['PYTHONPATH'] = os.getcwd() + "/src"

    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode == 2
    assert "[FAIL]" in res.stdout
