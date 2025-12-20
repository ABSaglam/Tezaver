"""
MX-20004: Matrix Agent

Handles Matrix engine jobs: import, sniper, war, approve/export.
"""

from typing import Dict, Any
from tezaver.platform.agents.base import BaseAgent, AgentConfig
from tezaver.platform.jobs.queue import Job


class MatrixAgent(BaseAgent):
    """Matrix engine agent."""
    
    def __init__(self, config: AgentConfig, matrix_home: str = ".tezaver_matrix"):
        super().__init__(config)
        self.matrix_home = matrix_home
        
    def setup_handlers(self) -> None:
        self.register_handler("MATRIX_IMPORT_CANDIDATE", self._handle_import_candidate)
        self.register_handler("MATRIX_RUN_SNIPER", self._handle_run_sniper)
        self.register_handler("MATRIX_RUN_WAR", self._handle_run_war)
        self.register_handler("MATRIX_APPROVE_EXPORT", self._handle_approve_export)
        
    def _handle_import_candidate(self, job: Job) -> Dict[str, Any]:
        """Import candidate from bus artifact to matrix home."""
        artifact_path = job.payload.get("artifact_path")
        if not artifact_path:
            return {"error": "missing artifact_path"}
            
        # Get artifact from bus
        artifact = self.bus.get_json(artifact_path)
        if not artifact:
            return {"error": f"artifact not found: {artifact_path}"}
            
        # Import to matrix home
        try:
            from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
            store = FileCandidateStore(self.matrix_home)
            
            candidate_id = artifact.get("candidate_id", job.job_id)
            store.save(candidate_id, artifact)
            
            return {"status": "imported", "candidate_id": candidate_id}
        except Exception as e:
            return {"error": str(e)}
            
    def _handle_run_sniper(self, job: Job) -> Dict[str, Any]:
        """Run sniper on candidate."""
        candidate_id = job.payload.get("candidate_id")
        if not candidate_id:
            return {"error": "missing candidate_id"}
            
        try:
            from tezaver.matrix.core.sniper_engine import sniper_run
            result = sniper_run(self.matrix_home, candidate_id)
            return {"status": "completed", "result": result}
        except Exception as e:
            return {"error": str(e)}
            
    def _handle_run_war(self, job: Job) -> Dict[str, Any]:
        """Run war game on candidate."""
        candidate_id = job.payload.get("candidate_id")
        ticks = job.payload.get("ticks", 10)
        
        if not candidate_id:
            return {"error": "missing candidate_id"}
            
        try:
            from tezaver.matrix.core.war_game import war_game_run
            result = war_game_run(self.matrix_home, candidate_id, ticks=ticks)
            return {"status": "completed", "result": result}
        except Exception as e:
            return {"error": str(e)}
            
    def _handle_approve_export(self, job: Job) -> Dict[str, Any]:
        """Approve candidate and export."""
        candidate_id = job.payload.get("candidate_id")
        if not candidate_id:
            return {"error": "missing candidate_id"}
            
        try:
            from tezaver.matrix.core.approve import approve_candidate
            from tezaver.matrix.core.export_v1 import export_cloud_strategy
            
            approve_result = approve_candidate(self.matrix_home, candidate_id)
            export_result = export_cloud_strategy(self.matrix_home, candidate_id)
            
            # Put export artifact on bus
            export_path = f"artifacts/matrix/exports/{candidate_id}.json"
            self.bus.put_json(export_path, export_result)
            
            return {
                "status": "approved_and_exported",
                "candidate_id": candidate_id,
                "export_artifact": export_path,
            }
        except Exception as e:
            return {"error": str(e)}
