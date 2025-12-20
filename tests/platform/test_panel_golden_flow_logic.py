"""
MX-23001: Test for Panel Golden Flow Logic
"""

import os
import json
import pytest
from tezaver.platform.bus.adapter import FsBusAdapter
from tezaver.ui.platform_golden_tab import run_golden_flow, StepResult, enqueue_job, get_outbox_result


class MockHTTPServer:
    """Mock HTTP server for testing without real agents."""
    
    def __init__(self, bus_root: str):
        self.bus = FsBusAdapter(bus_root)
        
    def process_mac_jobs(self):
        """Process mac jobs in inbox."""
        inbox_path = os.path.join(self.bus.root, "jobs", "mac", "inbox")
        if not os.path.exists(inbox_path):
            return
            
        for f in os.listdir(inbox_path):
            if f.endswith(".json"):
                job = self.bus.get_json(f"jobs/mac/inbox/{f}")
                if job["job_type"] == "MAC_BUILD_CANDIDATE":
                    result = {
                        "ok": True,
                        "candidate_id": "TEST_CAND_001",
                        "artifact_path": "artifacts/mac/candidates/TEST_CAND_001.json",
                    }
                    self.bus.put_json(result["artifact_path"], {
                        "candidate_id": "TEST_CAND_001",
                        "symbol": job["payload"].get("symbol", "BTCUSDT"),
                    })
                    
                    outbox = {
                        "job_id": job["job_id"],
                        "status": "success",
                        "result": result,
                        "completed_at": 1234567890,
                        "error": None,
                    }
                    self.bus.put_json(f"jobs/mac/outbox/{job['job_id']}.json", outbox)
                    self.bus.delete(f"jobs/mac/inbox/{f}")
                    
    def process_matrix_jobs(self):
        """Process matrix jobs in inbox."""
        inbox_path = os.path.join(self.bus.root, "jobs", "matrix", "inbox")
        if not os.path.exists(inbox_path):
            return
            
        for f in os.listdir(inbox_path):
            if f.endswith(".json"):
                job = self.bus.get_json(f"jobs/matrix/inbox/{f}")
                
                if job["job_type"] == "MATRIX_IMPORT_CANDIDATE":
                    result = {"ok": True, "candidate_id": "TEST_CAND_001"}
                elif job["job_type"] == "MATRIX_RUN_SNIPER":
                    result = {"ok": True, "run_id": "run_001", "verdict": "PASS"}
                elif job["job_type"] == "MATRIX_APPROVE_EXPORT":
                    result = {"ok": True, "bus_export_path": "artifacts/matrix/exports/TEST_CAND_001.json"}
                    self.bus.put_json(result["bus_export_path"], {"export_id": "EXP_001"})
                else:
                    result = {"ok": False}
                    
                outbox = {
                    "job_id": job["job_id"],
                    "status": "success",
                    "result": result,
                    "completed_at": 1234567890,
                    "error": None,
                }
                self.bus.put_json(f"jobs/matrix/outbox/{job['job_id']}.json", outbox)
                self.bus.delete(f"jobs/matrix/inbox/{f}")
                
    def process_cloud_jobs(self):
        """Process cloud jobs in inbox."""
        inbox_path = os.path.join(self.bus.root, "jobs", "cloud", "inbox")
        if not os.path.exists(inbox_path):
            return
            
        for f in os.listdir(inbox_path):
            if f.endswith(".json"):
                job = self.bus.get_json(f"jobs/cloud/inbox/{f}")
                
                if job["job_type"] == "CLOUD_IMPORT_STRATEGY":
                    result = {"ok": True, "strategy_id": "STRAT_001", "status": "PAUSED"}
                elif job["job_type"] == "CLOUD_SET_STATUS":
                    result = {"ok": True, "strategy_id": "STRAT_001", "status": "ACTIVE"}
                elif job["job_type"] == "CLOUD_RUNTIME_TICK":
                    result = {"ok": True, "ticks_done": 2}
                else:
                    result = {"ok": False}
                    
                outbox = {
                    "job_id": job["job_id"],
                    "status": "success",
                    "result": result,
                    "completed_at": 1234567890,
                    "error": None,
                }
                self.bus.put_json(f"jobs/cloud/outbox/{job['job_id']}.json", outbox)
                self.bus.delete(f"jobs/cloud/inbox/{f}")


class TestPanelGoldenFlowLogic:
    """Test panel golden flow logic."""
    
    def test_enqueue_job(self, tmp_path):
        """Test job enqueue creates file in inbox."""
        bus = FsBusAdapter(str(tmp_path))
        
        job_id = enqueue_job(bus, "mac", "MAC_BUILD_CANDIDATE", {"symbol": "BTCUSDT"})
        
        assert job_id.startswith("job_")
        assert bus.exists(f"jobs/mac/inbox/{job_id}.json")
        
    def test_get_outbox_result(self, tmp_path):
        """Test get_outbox_result reads result."""
        bus = FsBusAdapter(str(tmp_path))
        
        # Put result
        bus.put_json("jobs/mac/outbox/job_test.json", {"result": {"ok": True}})
        
        result = get_outbox_result(bus, "mac", "job_test", timeout=1)
        
        assert result is not None
        assert result["result"]["ok"] is True
        
    def test_get_outbox_result_timeout(self, tmp_path):
        """Test get_outbox_result returns None on timeout."""
        bus = FsBusAdapter(str(tmp_path))
        
        result = get_outbox_result(bus, "mac", "nonexistent", timeout=0.5)
        
        assert result is None
        
    def test_step_result_dataclass(self):
        """Test StepResult dataclass."""
        step = StepResult("Test Step", "OK", "message", {"key": "value"})
        
        assert step.name == "Test Step"
        assert step.status == "OK"
        assert step.message == "message"
        assert step.data["key"] == "value"
