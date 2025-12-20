"""
MX-23004: Test for MatrixAgent Release/Rehearsal Jobs
"""

import os
import json
import pytest
from tezaver.platform.bus.adapter import FsBusAdapter
from tezaver.platform.jobs.queue import create_job, enqueue_job, list_jobs
from tezaver.platform.agents.matrix_agent import MatrixAgent, MatrixAgentConfig


class TestMatrixAgentReleaseRehearsalJobs:
    """Test release and rehearsal check jobs."""
    
    def test_release_check_pass(self, tmp_path):
        """Test release check returns PASS for valid candidate."""
        bus_root = str(tmp_path / "bus")
        matrix_home = str(tmp_path / "matrix")
        
        # Setup
        os.makedirs(os.path.join(matrix_home, "candidates", "CAND_001"))
        os.makedirs(os.path.join(matrix_home, "approved", "CAND_001"))
        os.makedirs(os.path.join(matrix_home, "runs", "sniper_CAND_001_123"))
        
        # Create sniper scorecard with PASS
        with open(os.path.join(matrix_home, "runs", "sniper_CAND_001_123", "scorecard.json"), "w") as f:
            json.dump({"verdict": "PASS"}, f)
            
        config = MatrixAgentConfig(
            agent_name="matrix",
            bus_root=bus_root,
            token="",
            matrix_home=matrix_home,
        )
        
        agent = MatrixAgent(config)
        agent.setup_handlers()
        
        # Enqueue release check job
        job = create_job("MATRIX_RELEASE_CHECK", "matrix", {
            "candidate_id": "CAND_001",
        })
        enqueue_job(agent.bus, job)
        agent.scan_inbox()
        
        # Check result
        outbox = list_jobs(agent.bus, "matrix", "outbox")
        assert len(outbox) == 1
        result = outbox[0]["result"]
        
        assert result["ok"] is True
        assert result["release_status"] == "PASS"
        assert len(result["fail_codes"]) == 0
        
    def test_release_check_fail_not_approved(self, tmp_path):
        """Test release check returns FAIL for non-approved candidate."""
        bus_root = str(tmp_path / "bus")
        matrix_home = str(tmp_path / "matrix")
        
        # Setup - candidate exists but NOT approved
        os.makedirs(os.path.join(matrix_home, "candidates", "CAND_002"))
        
        config = MatrixAgentConfig(
            agent_name="matrix",
            bus_root=bus_root,
            token="",
            matrix_home=matrix_home,
        )
        
        agent = MatrixAgent(config)
        agent.setup_handlers()
        
        job = create_job("MATRIX_RELEASE_CHECK", "matrix", {
            "candidate_id": "CAND_002",
        })
        enqueue_job(agent.bus, job)
        agent.scan_inbox()
        
        outbox = list_jobs(agent.bus, "matrix", "outbox")
        result = outbox[0]["result"]
        
        assert result["ok"] is True
        assert result["release_status"] == "FAIL"
        assert "NOT_APPROVED" in result["fail_codes"]
        
    def test_rehearsal_check_go(self, tmp_path):
        """Test rehearsal check returns GO for valid setup."""
        bus_root = str(tmp_path / "bus")
        matrix_home = str(tmp_path / "matrix")
        
        # Setup
        os.makedirs(os.path.join(matrix_home, "exports", "CAND_003"))
        os.makedirs(os.path.join(matrix_home, "approved", "CAND_003"))
        with open(os.path.join(matrix_home, "approved", "CAND_003", "manifest.json"), "w") as f:
            json.dump({"candidate_id": "CAND_003"}, f)
            
        config = MatrixAgentConfig(
            agent_name="matrix",
            bus_root=bus_root,
            token="",
            matrix_home=matrix_home,
        )
        
        agent = MatrixAgent(config)
        agent.setup_handlers()
        
        job = create_job("MATRIX_REHEARSAL_CHECK", "matrix", {
            "candidate_id": "CAND_003",
            "mode": "PAPER",
        })
        enqueue_job(agent.bus, job)
        agent.scan_inbox()
        
        outbox = list_jobs(agent.bus, "matrix", "outbox")
        result = outbox[0]["result"]
        
        assert result["ok"] is True
        assert result["rehearsal"] == "GO"
        assert result["mode"] == "PAPER"
        
    def test_rehearsal_check_no_go_no_export(self, tmp_path):
        """Test rehearsal check returns NO_GO when no export."""
        bus_root = str(tmp_path / "bus")
        matrix_home = str(tmp_path / "matrix")
        
        os.makedirs(matrix_home)
        
        config = MatrixAgentConfig(
            agent_name="matrix",
            bus_root=bus_root,
            token="",
            matrix_home=matrix_home,
        )
        
        agent = MatrixAgent(config)
        agent.setup_handlers()
        
        job = create_job("MATRIX_REHEARSAL_CHECK", "matrix", {
            "candidate_id": "CAND_MISSING",
        })
        enqueue_job(agent.bus, job)
        agent.scan_inbox()
        
        outbox = list_jobs(agent.bus, "matrix", "outbox")
        result = outbox[0]["result"]
        
        assert result["ok"] is True
        assert result["rehearsal"] == "NO_GO"
        assert "NO_EXPORT" in result["fail_codes"]
