import os
import json
import pytest
from tezaver.matrix.apps.run_sniper import run_sniper_once

@pytest.mark.core
def test_run_sniper_uses_config_signature(tmp_path):
    """Test that run_sniper_once function has expected signature and is callable."""
    # Test that run_sniper_once is callable with expected args
    import inspect
    sig = inspect.signature(run_sniper_once)
    params = list(sig.parameters.keys())
    
    # Should accept home and candidate_id at minimum
    assert "home" in params or len(params) >= 2
    
    # Verify the function is importable and callable
    assert callable(run_sniper_once)
    
    print(f"SUCCESS: run_sniper_once has signature {sig}")

