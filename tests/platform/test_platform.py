"""
Tests for MX-20001-20008: Tezaver Platform
"""

import json
import pytest
from tezaver.platform.bus.adapter import FsBusAdapter
from tezaver.platform.jobs.queue import (
    Job, create_job, enqueue_job, claim_next_job, 
    write_result, write_deadletter, list_jobs
)


class TestBusAdapter:
    """MX-20001: Bus Adapter tests."""
    
    def test_put_get_json(self, tmp_path):
        bus = FsBusAdapter(str(tmp_path))
        
        obj = {"key": "value", "num": 42}
        bus.put_json("test/data.json", obj)
        
        result = bus.get_json("test/data.json")
        assert result == obj
        
    def test_list(self, tmp_path):
        bus = FsBusAdapter(str(tmp_path))
        
        bus.put_json("items/a.json", {"id": "a"})
        bus.put_json("items/b.json", {"id": "b"})
        
        items = bus.list("items")
        assert len(items) == 2
        assert "items/a.json" in items
        assert "items/b.json" in items
        
    def test_exists(self, tmp_path):
        bus = FsBusAdapter(str(tmp_path))
        
        assert not bus.exists("missing.json")
        bus.put_json("exists.json", {})
        assert bus.exists("exists.json")
        
    def test_append_ndjson(self, tmp_path):
        bus = FsBusAdapter(str(tmp_path))
        
        bus.append_ndjson("events.ndjson", {"event": 1})
        bus.append_ndjson("events.ndjson", {"event": 2})
        
        with open(tmp_path / "events.ndjson") as f:
            lines = f.readlines()
            
        assert len(lines) == 2
        assert json.loads(lines[0])["event"] == 1
        assert json.loads(lines[1])["event"] == 2


class TestJobQueue:
    """MX-20002: Job Queue tests."""
    
    def test_create_and_enqueue_job(self, tmp_path):
        bus = FsBusAdapter(str(tmp_path))
        
        job = create_job("TEST_JOB", "matrix", {"data": "test"})
        job_id = enqueue_job(bus, job)
        
        assert job_id.startswith("job_")
        assert bus.exists(f"jobs/matrix/inbox/{job_id}.json")
        
    def test_claim_job_atomic(self, tmp_path):
        bus = FsBusAdapter(str(tmp_path))
        
        job = create_job("TEST_JOB", "matrix", {"data": "test"})
        enqueue_job(bus, job)
        
        claimed = claim_next_job(bus, "matrix", max_n=1)
        
        assert len(claimed) == 1
        assert claimed[0].job_id == job.job_id
        
        # Job should be in processing, not inbox
        assert not bus.exists(f"jobs/matrix/inbox/{job.job_id}.json")
        assert bus.exists(f"jobs/matrix/processing/{job.job_id}.json")
        
    def test_write_result(self, tmp_path):
        bus = FsBusAdapter(str(tmp_path))
        
        job = create_job("TEST_JOB", "matrix", {})
        enqueue_job(bus, job)
        claim_next_job(bus, "matrix")
        
        write_result(bus, "matrix", job.job_id, {"output": "success"})
        
        # Should be in outbox, not processing
        assert not bus.exists(f"jobs/matrix/processing/{job.job_id}.json")
        assert bus.exists(f"jobs/matrix/outbox/{job.job_id}.json")
        
    def test_write_deadletter(self, tmp_path):
        bus = FsBusAdapter(str(tmp_path))
        
        job = create_job("TEST_JOB", "matrix", {})
        enqueue_job(bus, job)
        claim_next_job(bus, "matrix")
        
        write_deadletter(bus, "matrix", job.job_id, "test error")
        
        # Should be in deadletter
        assert bus.exists(f"jobs/matrix/deadletter/{job.job_id}.json")
        
        data = bus.get_json(f"jobs/matrix/deadletter/{job.job_id}.json")
        assert data["deadletter_reason"] == "test error"


class TestAgentKit:
    """MX-20003: Agent Kit tests."""
    
    def test_agent_health(self, tmp_path):
        from tezaver.platform.agents.base import BaseAgent, AgentConfig
        
        class TestAgent(BaseAgent):
            def setup_handlers(self):
                pass
                
        config = AgentConfig(
            agent_name="test",
            bus_root=str(tmp_path),
            token="secret",
        )
        
        agent = TestAgent(config)
        health = agent.health()
        
        assert health["agent"] == "test"
        assert health["status"] == "healthy"
        
    def test_agent_scan_inbox(self, tmp_path):
        from tezaver.platform.agents.base import BaseAgent, AgentConfig
        
        class TestAgent(BaseAgent):
            def setup_handlers(self):
                self.register_handler("ECHO", lambda job: {"echo": job.payload})
                
        config = AgentConfig(
            agent_name="test",
            bus_root=str(tmp_path),
            token="",
        )
        
        agent = TestAgent(config)
        agent.setup_handlers()
        
        # Enqueue job
        job = create_job("ECHO", "test", {"message": "hello"})
        enqueue_job(agent.bus, job)
        
        # Scan inbox
        processed = agent.scan_inbox()
        
        assert processed == 1
        
        # Check result in outbox
        outbox_jobs = list_jobs(agent.bus, "test", "outbox")
        assert len(outbox_jobs) == 1
        assert outbox_jobs[0]["result"]["echo"]["message"] == "hello"


class TestMacAgent:
    """MX-20005: Mac Agent tests."""
    
    def test_build_candidate(self, tmp_path):
        from tezaver.platform.agents.mac_agent import MacAgent
        from tezaver.platform.agents.base import AgentConfig
        
        config = AgentConfig(
            agent_name="mac",
            bus_root=str(tmp_path),
            token="",
        )
        
        agent = MacAgent(config)
        agent.setup_handlers()
        
        # Enqueue build job
        job = create_job("MAC_BUILD_CANDIDATE", "mac", {
            "symbol": "ETHUSDT",
            "timeframe": "1h",
        })
        enqueue_job(agent.bus, job)
        
        # Process
        agent.scan_inbox()
        
        # Check result
        outbox_jobs = list_jobs(agent.bus, "mac", "outbox")
        assert len(outbox_jobs) == 1
        
        result = outbox_jobs[0]["result"]
        assert result["status"] == "built"
        assert "ETHUSDT" in result["candidate_id"]
        
        # Check artifact was written
        assert agent.bus.exists(result["artifact_path"])
