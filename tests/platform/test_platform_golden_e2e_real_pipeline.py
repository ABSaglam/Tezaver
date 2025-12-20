"""
MX-21010: Golden E2E Test - Mac -> Matrix -> Cloud Pipeline
"""

import os
import json
import pytest
from tezaver.platform.bus.adapter import FsBusAdapter
from tezaver.platform.jobs.queue import create_job, enqueue_job, list_jobs
from tezaver.platform.agents.mac_agent import MacAgent
from tezaver.platform.agents.matrix_agent import MatrixAgent, MatrixAgentConfig
from tezaver.platform.agents.cloud_agent import CloudAgent, CloudAgentConfig
from tezaver.platform.agents.base import AgentConfig


class TestGoldenE2ERealPipeline:
    """Golden E2E test: Mac -> Matrix -> Cloud."""
    
    def test_full_pipeline_mac_matrix_cloud(self, tmp_path):
        """
        Full pipeline test:
        1) MacAgent builds candidate
        2) MatrixAgent imports -> sniper -> approve_export
        3) CloudAgent imports strategy -> set ACTIVE -> tick
        """
        bus_root = str(tmp_path / "bus")
        matrix_home = str(tmp_path / "matrix_home")
        cloud_home = str(tmp_path / "cloud_home")
        
        # Create directories
        os.makedirs(matrix_home)
        os.makedirs(cloud_home)
        
        # 1. MAC AGENT: Build candidate
        mac_config = AgentConfig(agent_name="mac", bus_root=bus_root, token="")
        mac_agent = MacAgent(mac_config)
        mac_agent.setup_handlers()
        
        build_job = create_job("MAC_BUILD_CANDIDATE", "mac", {
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "params": {"entry": "breakout"},
        })
        enqueue_job(mac_agent.bus, build_job)
        mac_agent.scan_inbox()
        
        # Check Mac result
        mac_outbox = list_jobs(mac_agent.bus, "mac", "outbox")
        assert len(mac_outbox) == 1
        mac_result = mac_outbox[0]["result"]
        assert mac_result["ok"] is True
        artifact_path = mac_result["artifact_path"]
        candidate_id = mac_result["candidate_id"]
        
        # 2. MATRIX AGENT: Import -> Sniper -> Approve Export
        matrix_config = MatrixAgentConfig(
            agent_name="matrix",
            bus_root=bus_root,
            token="",
            matrix_home=matrix_home,
        )
        matrix_agent = MatrixAgent(matrix_config)
        matrix_agent.setup_handlers()
        
        # 2a. Import
        import_job = create_job("MATRIX_IMPORT_CANDIDATE", "matrix", {
            "artifact_path": artifact_path,
        })
        enqueue_job(matrix_agent.bus, import_job)
        matrix_agent.scan_inbox()
        
        # 2b. Sniper
        sniper_job = create_job("MATRIX_RUN_SNIPER", "matrix", {
            "candidate_id": candidate_id,
        })
        enqueue_job(matrix_agent.bus, sniper_job)
        matrix_agent.scan_inbox()
        
        # 2c. Approve Export
        approve_job = create_job("MATRIX_APPROVE_EXPORT", "matrix", {
            "candidate_id": candidate_id,
            "export": True,
        })
        enqueue_job(matrix_agent.bus, approve_job)
        matrix_agent.scan_inbox()
        
        # Check Matrix results
        matrix_outbox = list_jobs(matrix_agent.bus, "matrix", "outbox")
        assert len(matrix_outbox) == 3
        
        # Find approve result
        approve_result = next(j for j in matrix_outbox if j["job_id"] == approve_job.job_id)
        assert approve_result["result"]["ok"] is True
        assert approve_result["result"].get("bus_export_path")
        export_bus_path = approve_result["result"]["bus_export_path"]
        
        # Verify export exists on bus
        assert matrix_agent.bus.exists(export_bus_path)
        
        # 3. CLOUD AGENT: Import Strategy -> Set ACTIVE -> Tick
        cloud_config = CloudAgentConfig(
            agent_name="cloud",
            bus_root=bus_root,
            token="",
            cloud_home=cloud_home,
        )
        cloud_agent = CloudAgent(cloud_config)
        cloud_agent.setup_handlers()
        
        # 3a. Import Strategy
        import_strat_job = create_job("CLOUD_IMPORT_STRATEGY", "cloud", {
            "export_path": export_bus_path,
        })
        enqueue_job(cloud_agent.bus, import_strat_job)
        cloud_agent.scan_inbox()
        
        # Get strategy ID
        cloud_outbox = list_jobs(cloud_agent.bus, "cloud", "outbox")
        import_result = next(j for j in cloud_outbox if j["job_id"] == import_strat_job.job_id)
        assert import_result["result"]["ok"] is True
        strategy_id = import_result["result"]["strategy_id"]
        
        # 3b. Set ACTIVE
        activate_job = create_job("CLOUD_SET_STATUS", "cloud", {
            "strategy_id": strategy_id,
            "status": "ACTIVE",
        })
        enqueue_job(cloud_agent.bus, activate_job)
        cloud_agent.scan_inbox()
        
        # 3c. Runtime Tick
        tick_job = create_job("CLOUD_RUNTIME_TICK", "cloud", {"ticks": 2})
        enqueue_job(cloud_agent.bus, tick_job)
        cloud_agent.scan_inbox()
        
        # ASSERTIONS
        # 1. Export exists
        assert matrix_agent.bus.exists(export_bus_path)
        
        # 2. Cloud registry has strategy ACTIVE
        strat_path = os.path.join(cloud_home, "cloud_registry", "strategies", strategy_id, "strategy.json")
        assert os.path.exists(strat_path)
        with open(strat_path) as f:
            strat = json.load(f)
        assert strat["status_info"]["status"] == "ACTIVE"
        
        # 3. Cloud runtime wrote tick events
        events_path = os.path.join(bus_root, "events", "cloud.ndjson")
        assert os.path.exists(events_path)
        with open(events_path) as f:
            events = [json.loads(line) for line in f]
        tick_events = [e for e in events if e.get("kind") == "RUNTIME_TICK"]
        assert len(tick_events) >= 2
        
        # 4. Matrix home has candidate and runs
        assert os.path.exists(os.path.join(matrix_home, "candidates", candidate_id))
        assert os.path.exists(os.path.join(matrix_home, "runs"))
        assert os.path.exists(os.path.join(matrix_home, "approved", candidate_id))
