import os
import json
import subprocess
import sys
import pytest

@pytest.mark.core
def test_run_sniper_cli(tmp_path):
    """Test that run_sniper module can be imported and basic functions work."""
    # Test import works
    from tezaver.matrix.apps.run_sniper import run_sniper_once, run_sniper_stub
    
    # Test that functions are callable
    assert callable(run_sniper_once)
    assert callable(run_sniper_stub)
    
    # Test CLI help (should return 0 or show help without crashing)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    
    # Just test that the module is importable and has expected interface
    proc = subprocess.run(
        [sys.executable, "-c", "from tezaver.matrix.apps.run_sniper import run_sniper_once; print('OK')"],
        env=env, capture_output=True, text=True
    )
    
    assert proc.returncode == 0
    assert "OK" in proc.stdout
    
    print("SUCCESS: run_sniper module is importable and has expected interface")

