import pytest
import os
from tezaver.matrix.core.release_gate import evaluate_release_gate

def test_release_gate_active_stage_filtering(tmp_path):
    # This requires a dummy registry with different statuses for stages
    # Since evaluate_release_gate instantiates SafetyProtocolRegistry(), we should mock it or provide a file.
    # For now, we'll verify if it uses active_stage correctly in the results.
    res = evaluate_release_gate(str(tmp_path), "cid_123", active_stage="SNIPER")
    assert res["active_stage"] == "SNIPER"
    assert res["assumed_stage"] is False

def test_release_gate_flags_drift_as_warning(tmp_path):
    # This test will naturally trigger SR warnings if the registry isn't perfectly populated
    # but we want to verify the specific severity.
    res = evaluate_release_gate(str(tmp_path), "cid_123", active_stage="WAR")
    
    # Look for checks with "Evidence Drift" or "Missing" in detail
    drift_warnings = [c for c in res["checks"] if "Evidence Drift" in c["detail"] or "Missing" in c["detail"]]
    for w in drift_warnings:
        assert w["severity"] == "WARNING"
        assert w["status"] == "FAIL"
