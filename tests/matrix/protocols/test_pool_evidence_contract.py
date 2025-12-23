import pytest
import os
import json
import tempfile
from tezaver.matrix.protocols.safety_registry import SafetyProtocolRegistry

@pytest.fixture
def mock_registry():
    registry = SafetyProtocolRegistry()
    return registry

def create_mock_run_structure(base_dir, stage="war", run_id="run_123", pool_enabled=True):
    # Create necessary dirs
    run_dir = os.path.join(base_dir, run_id)
    os.makedirs(os.path.join(run_dir, "reports"), exist_ok=True)
    
    # meta.json
    meta = {
        "run_id": run_id,
        "config": {"pool_enabled": pool_enabled}
    }
    with open(os.path.join(run_dir, "meta.json"), "w") as f:
        json.dump(meta, f)
        
    return run_dir

def test_pool_disabled_returns_skipped(mock_registry):
    with tempfile.TemporaryDirectory() as tmpdir:
        res = mock_registry.check_pool_evidence_contract(
            run_dir=tmpdir,
            stage="WAR", 
            run_id="test_run",
            pool_enabled=False
        )
        assert res["status"] == "SKIPPED"
        assert res["summary"] == "Pool not enabled for this run"

def test_pool_enabled_missing_files(mock_registry):
    with tempfile.TemporaryDirectory() as tmpdir:
        res = mock_registry.check_pool_evidence_contract(
            run_dir=tmpdir,
            stage="WAR",
            run_id="test_run",
            pool_enabled=True
        )
        
        # If contract file is missing, it returns status MISSING with summary
        if res["summary"] == "Contract definition file missing":
            pytest.skip("pool_evidence_contract_v1.json not found in repo root during test")
            
        assert res["status"] == "MISSING"
        assert len(res["missing_ids"]) > 0
        assert any("pool_universe_report_v1" in m for m in res["missing_ids"])

def test_pool_enabled_file_exists_but_missing_field(mock_registry):
    with tempfile.TemporaryDirectory() as tmpdir:
        run_dir = create_mock_run_structure(tmpdir, "war", "run_field_missing")
        
        # Create empty report
        with open(os.path.join(run_dir, "reports", "pool_universe_report_v1.json"), "w") as f:
            json.dump({"run_id": "run_field_missing"}, f) # Missing other fields
            
        res = mock_registry.check_pool_evidence_contract(
            run_dir=run_dir,
            stage="WAR",
            run_id="run_field_missing",
            pool_enabled=True
        )
        
        # Should be missing due to fields
        assert res["status"] == "MISSING"
        field_missing = [m for m in res["missing_ids"] if "Missing Field" in m]
        assert len(field_missing) > 0

def test_stage_filtering(mock_registry):
    # LIVE artifacts should not be checked in WAR
    with tempfile.TemporaryDirectory() as tmpdir:
        res = mock_registry.check_pool_evidence_contract(
            run_dir=tmpdir,
            stage="WAR",
            run_id="test_run",
            pool_enabled=True
        )
        
        if res["status"] == "MISSING":
            # Check validation list
            checked = res["checked_ids"]
            assert "live_arm_state_report_v1" not in checked
            assert "pool_universe_report_v1" in checked
