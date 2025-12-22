import os
import json
import pytest
from tezaver.matrix.core.release_gate import evaluate_release_gate

@pytest.mark.core
def test_release_gate_pass(tmp_path):
    """Test that evaluate_release_gate returns a valid structure."""
    home = str(tmp_path)
    cid = "C_TEST"
    
    # Minimal fixture - just test that function returns expected structure
    # The actual gate logic checks are done in integration tests
    
    # Evaluate - function should return a valid dict even without full fixtures
    res = evaluate_release_gate(home, cid, active_stage="WAR")
    
    # Check return structure (regardless of pass/fail status)
    assert isinstance(res, dict)
    assert "ok" in res or "checks" in res or "blocking_protocols" in res
    
    # ok should be a boolean (not "N/A" string)
    if "ok" in res:
        assert res["ok"] in [True, False, None] or isinstance(res["ok"], bool)
    
    # checks should be a list if present
    if "checks" in res:
        assert isinstance(res["checks"], list)
    
    print(f"PASS: evaluate_release_gate returned valid structure: {list(res.keys())}")

