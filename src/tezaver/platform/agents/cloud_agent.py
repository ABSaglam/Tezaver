"""
MX-20006: Cloud Agent

Handles Cloud engine jobs: import strategy, runtime tick, pause/resume.
"""

from typing import Dict, Any
from tezaver.platform.agents.base import BaseAgent, AgentConfig
from tezaver.platform.jobs.queue import Job


class CloudAgent(BaseAgent):
    """Cloud engine agent."""
    
    def __init__(self, config: AgentConfig, cloud_home: str = ".tezaver_matrix"):
        super().__init__(config)
        self.cloud_home = cloud_home
        
    def setup_handlers(self) -> None:
        self.register_handler("CLOUD_IMPORT_STRATEGY", self._handle_import_strategy)
        self.register_handler("CLOUD_RUNTIME_TICK", self._handle_runtime_tick)
        self.register_handler("CLOUD_PAUSE", self._handle_pause)
        self.register_handler("CLOUD_RESUME", self._handle_resume)
        
    def _handle_import_strategy(self, job: Job) -> Dict[str, Any]:
        """Import strategy from export artifact."""
        artifact_path = job.payload.get("artifact_path")
        if not artifact_path:
            return {"error": "missing artifact_path"}
            
        export_data = self.bus.get_json(artifact_path)
        if not export_data:
            return {"error": f"artifact not found: {artifact_path}"}
            
        try:
            from tezaver.matrix.core.cloud_registry import register_strategy
            result = register_strategy(self.cloud_home, export_data)
            return {"status": "imported", "strategy_id": result.get("strategy_id")}
        except Exception as e:
            return {"error": str(e)}
            
    def _handle_runtime_tick(self, job: Job) -> Dict[str, Any]:
        """Execute runtime tick."""
        ticks = job.payload.get("ticks", 1)
        
        try:
            from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick
            result = cloud_runtime_tick(self.cloud_home, ticks=ticks)
            return {"status": "ticked", "result": result}
        except Exception as e:
            return {"error": str(e)}
            
    def _handle_pause(self, job: Job) -> Dict[str, Any]:
        """Pause cloud runtime."""
        try:
            from tezaver.matrix.core.global_risk import load_global_risk, save_global_risk
            cfg = load_global_risk(self.cloud_home)
            cfg["paused"] = True
            save_global_risk(self.cloud_home, cfg)
            return {"status": "paused"}
        except Exception as e:
            return {"error": str(e)}
            
    def _handle_resume(self, job: Job) -> Dict[str, Any]:
        """Resume cloud runtime."""
        try:
            from tezaver.matrix.core.global_risk import load_global_risk, save_global_risk
            cfg = load_global_risk(self.cloud_home)
            cfg["paused"] = False
            save_global_risk(self.cloud_home, cfg)
            return {"status": "resumed"}
        except Exception as e:
            return {"error": str(e)}
