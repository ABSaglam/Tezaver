import os
import json
import pytest
import subprocess

def test_recover_cli_writes_report(tmp_path):
    home = str(tmp_path)
    
    cmd = [
        "python3", "-m", "tezaver.matrix.apps.recover",
        "--home", home
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() + "/src"
    
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    assert res.returncode == 0
    assert "RECOVERY COMPLETE" in res.stdout
    
    rp = tmp_path / "ops" / "recovery" / "latest.json"
    assert rp.exists()
    with open(rp) as f:
        rep = json.load(f)
        assert rep["ok"] == True
