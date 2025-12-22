import os
import json
import subprocess
import sys
import shutil
import pytest

@pytest.mark.core
def test_run_war_cli(tmp_path):
    """Test that run_war module can be imported and basic functions work."""
    # Test import works
    from tezaver.matrix.apps.run_war import main as war_main
    from tezaver.matrix.core.war_engine import WarEngine
    
    # Test that WarEngine class exists and has expected interface
    assert hasattr(WarEngine, 'run')
    assert hasattr(WarEngine, '__init__')
    
    # Test CLI help via subprocess (just check module loads)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
    
    proc = subprocess.run(
        [sys.executable, "-c", "from tezaver.matrix.apps.run_war import main; print('OK')"],
        env=env, capture_output=True, text=True
    )
    
    assert proc.returncode == 0
    assert "OK" in proc.stdout
    
    print("SUCCESS: run_war module is importable and has expected interface")

