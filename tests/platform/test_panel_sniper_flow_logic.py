"""
MX-23002: Test for Panel Sniper Flow Logic
"""

import os
import json
import pytest
from tezaver.platform.bus.adapter import FsBusAdapter
from tezaver.ui.platform_sniper_tab import (
    run_candidate_sniper_flow, StepResult, enqueue_job, 
    get_outbox_result, list_candidate_artifacts
)


class TestPanelSniperFlowLogic:
    """Test panel sniper flow logic."""
    
    def test_enqueue_job(self, tmp_path):
        """Test job enqueue creates file in inbox."""
        bus = FsBusAdapter(str(tmp_path))
        
        job_id = enqueue_job(bus, "matrix", "MATRIX_IMPORT_CANDIDATE", {"artifact_path": "test.json"})
        
        assert job_id.startswith("job_")
        assert bus.exists(f"jobs/matrix/inbox/{job_id}.json")
        
    def test_list_candidate_artifacts(self, tmp_path):
        """Test listing candidate artifacts."""
        bus = FsBusAdapter(str(tmp_path))
        
        # Create some artifacts
        bus.put_json("artifacts/mac/candidates/cand_001.json", {"id": "001"})
        bus.put_json("artifacts/mac/candidates/cand_002.json", {"id": "002"})
        
        artifacts = list_candidate_artifacts(bus)
        
        assert len(artifacts) == 2
        assert any("cand_001.json" in a for a in artifacts)
        
    def test_list_candidate_artifacts_empty(self, tmp_path):
        """Test listing returns empty when no artifacts."""
        bus = FsBusAdapter(str(tmp_path))
        
        artifacts = list_candidate_artifacts(bus)
        
        assert artifacts == []
        
    def test_step_result_dataclass(self):
        """Test StepResult dataclass."""
        step = StepResult("Import", "OK", "done", {"candidate_id": "C001"})
        
        assert step.name == "Import"
        assert step.status == "OK"
        assert step.data["candidate_id"] == "C001"
