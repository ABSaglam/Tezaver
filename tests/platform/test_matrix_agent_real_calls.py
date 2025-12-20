"""
MX-21004: Tests for MatrixAgent real V4 calls.
"""

import os
import json
import pytest
from tezaver.platform.bus.adapter import FsBusAdapter
from tezaver.platform.jobs.queue import create_job, enqueue_job, list_jobs
from tezaver.platform.agents.matrix_agent import MatrixAgent, MatrixAgentConfig


class TestMatrixAgentRealCalls:
    """Test MatrixAgent with real V4 calls."""
    
    def test_import_and_sniper_flow(self, tmp_path):
        """Test import candidate then run sniper."""
        bus_root = str(tmp_path / "bus")
        matrix_home = str(tmp_path / "matrix_home")
        
        # Create matrix home
        os.makedirs(matrix_home)
        os.makedirs(os.path.join(matrix_home, "candidates"))
        
        # Create config
        config = MatrixAgentConfig(
            agent_name="matrix",
            bus_root=bus_root,
            token="",
            matrix_home=matrix_home,
        )
        
        agent = MatrixAgent(config)
        agent.setup_handlers()
        
        # 1. Create sample candidate artifact
        sample_candidate = {
            "candidate_id": "TEST_CAND_001",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "params": {"entry": "breakout", "sl_pct": 0.02},
        }
        artifact_path = "artifacts/mac/candidates/TEST_CAND_001.json"
        agent.bus.put_json(artifact_path, sample_candidate)
        
        # 2. Enqueue IMPORT job
        import_job = create_job("MATRIX_IMPORT_CANDIDATE", "matrix", {
            "artifact_path": artifact_path,
        })
        enqueue_job(agent.bus, import_job)
        
        # 3. Scan inbox (process import)
        agent.scan_inbox()
        
        # 4. Check outbox
        outbox = list_jobs(agent.bus, "matrix", "outbox")
        assert len(outbox) == 1
        assert outbox[0]["result"]["ok"] is True
        assert outbox[0]["result"]["candidate_id"] == "TEST_CAND_001"
        
        # 5. Verify candidate in matrix_home
        cand_dir = os.path.join(matrix_home, "candidates", "TEST_CAND_001")
        assert os.path.exists(cand_dir)
        
        # 6. Enqueue SNIPER job
        sniper_job = create_job("MATRIX_RUN_SNIPER", "matrix", {
            "candidate_id": "TEST_CAND_001",
        })
        enqueue_job(agent.bus, sniper_job)
        
        # 7. Scan inbox (process sniper)
        agent.scan_inbox()
        
        # 8. Check outbox (should have 2 jobs now)
        outbox = list_jobs(agent.bus, "matrix", "outbox")
        assert len(outbox) == 2
        
        # Find sniper result
        sniper_result = next(j for j in outbox if j["job_id"] == sniper_job.job_id)
        assert sniper_result["result"]["ok"] is True
        assert "run_id" in sniper_result["result"]
        
        # 9. Verify run in matrix_home
        runs_dir = os.path.join(matrix_home, "runs")
        assert os.path.exists(runs_dir)
        assert len(os.listdir(runs_dir)) >= 1
        
    def test_import_missing_artifact_fails(self, tmp_path):
        """Test import fails gracefully for missing artifact."""
        bus_root = str(tmp_path / "bus")
        matrix_home = str(tmp_path / "matrix_home")
        
        os.makedirs(matrix_home)
        
        config = MatrixAgentConfig(
            agent_name="matrix",
            bus_root=bus_root,
            token="",
            matrix_home=matrix_home,
        )
        
        agent = MatrixAgent(config)
        agent.setup_handlers()
        
        # Enqueue import with missing artifact
        job = create_job("MATRIX_IMPORT_CANDIDATE", "matrix", {
            "artifact_path": "nonexistent/path.json",
        })
        enqueue_job(agent.bus, job)
        
        agent.scan_inbox()
        
        outbox = list_jobs(agent.bus, "matrix", "outbox")
        assert len(outbox) == 1
        assert outbox[0]["result"]["ok"] is False
        assert "not found" in outbox[0]["result"]["error"]
        
    def test_events_logged_to_bus(self, tmp_path):
        """Test that job events are logged to bus."""
        bus_root = str(tmp_path / "bus")
        matrix_home = str(tmp_path / "matrix_home")
        
        os.makedirs(matrix_home)
        os.makedirs(os.path.join(matrix_home, "candidates"))
        
        config = MatrixAgentConfig(
            agent_name="matrix",
            bus_root=bus_root,
            token="",
            matrix_home=matrix_home,
        )
        
        agent = MatrixAgent(config)
        agent.setup_handlers()
        
        # Create and run import job
        artifact = {"candidate_id": "EVT_TEST", "symbol": "ETHUSDT"}
        agent.bus.put_json("artifacts/test.json", artifact)
        
        job = create_job("MATRIX_IMPORT_CANDIDATE", "matrix", {
            "artifact_path": "artifacts/test.json",
        })
        enqueue_job(agent.bus, job)
        agent.scan_inbox()
        
        # Check events log
        events_path = os.path.join(bus_root, "events", "matrix.ndjson")
        assert os.path.exists(events_path)
        
        with open(events_path) as f:
            events = [json.loads(line) for line in f]
            
        # Should have JOB_START and JOB_OK
        kinds = [e["kind"] for e in events]
        assert "JOB_START" in kinds
        assert "JOB_OK" in kinds
        
    def test_trace_included_in_result(self, tmp_path):
        """Test that trace info is included in results."""
        bus_root = str(tmp_path / "bus")
        matrix_home = str(tmp_path / "matrix_home")
        
        os.makedirs(matrix_home)
        os.makedirs(os.path.join(matrix_home, "candidates"))
        
        config = MatrixAgentConfig(
            agent_name="matrix",
            bus_root=bus_root,
            token="",
            matrix_home=matrix_home,
            engine_version="v4.test",
        )
        
        agent = MatrixAgent(config)
        agent.setup_handlers()
        
        artifact = {"candidate_id": "TRACE_TEST", "symbol": "BTCUSDT"}
        agent.bus.put_json("artifacts/trace.json", artifact)
        
        job = create_job("MATRIX_IMPORT_CANDIDATE", "matrix", {
            "artifact_path": "artifacts/trace.json",
        })
        enqueue_job(agent.bus, job)
        agent.scan_inbox()
        
        outbox = list_jobs(agent.bus, "matrix", "outbox")
        result = outbox[0]["result"]
        
        assert "trace" in result
        assert result["trace"]["engine_version"] == "v4.test"
        assert "config_signature" in result["trace"]
