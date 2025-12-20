import os
import json
import pytest
from tezaver.matrix.core.preflight import run_preflight

def test_preflight_writes_report(tmp_path):
    home = str(tmp_path)
    # 1. Run Core
    rep = run_preflight(home)
    assert rep["ok"] == True
    
    # 2. Check Dirs Created
    assert os.path.exists(tmp_path / "runs")
    assert os.path.exists(tmp_path / "cloud_registry" / "strategies")
    
    # 3. Test CLI (subprocess to verify report writing)
    # Or just call main logic if refactored.
    # Let's trust core logic returns dict, CLI writes it.
    # We can mock cli call?
    # subprocess preferred for CLI tool test.
    
    import subprocess
    cmd = [
        "python", "-m", "tezaver.matrix.apps.preflight_check",
        "--home", home
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() + "/src"
    
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode == 0
    assert "PREFLIGHT PASS" in res.stdout
    
    # Check File
    rep_path = tmp_path / "ops" / "preflight" / "latest.json"
    assert rep_path.exists()
    with open(rep_path) as f:
        data = json.load(f)
        assert data["ok"] == True
