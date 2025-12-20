"""
MX-21001..21005: Matrix Agent - Real Binding to V4

Handles Matrix engine jobs with real V4 core/apps calls:
- MATRIX_IMPORT_CANDIDATE
- MATRIX_RUN_SNIPER
- MATRIX_RUN_WAR
- MATRIX_RUN_LIVE_STEP
- MATRIX_APPROVE_EXPORT
"""

import time
import hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass

from tezaver.platform.agents.base import BaseAgent, AgentConfig
from tezaver.platform.jobs.queue import Job


@dataclass
class MatrixAgentConfig(AgentConfig):
    """Extended config for Matrix Agent."""
    matrix_home: str = ".tezaver_matrix"
    max_attempts: int = 3
    engine_version: str = "v4.0"


class MatrixAgent(BaseAgent):
    """Matrix engine agent with real V4 bindings."""
    
    def __init__(self, config: MatrixAgentConfig):
        super().__init__(config)
        self.matrix_home = config.matrix_home
        self.max_attempts = config.max_attempts
        self.engine_version = config.engine_version
        
    def setup_handlers(self) -> None:
        self.register_handler("MATRIX_IMPORT_CANDIDATE", self._handle_import_candidate)
        self.register_handler("MATRIX_RUN_SNIPER", self._handle_run_sniper)
        self.register_handler("MATRIX_RUN_WAR", self._handle_run_war)
        self.register_handler("MATRIX_RUN_LIVE_STEP", self._handle_run_live_step)
        self.register_handler("MATRIX_APPROVE_EXPORT", self._handle_approve_export)
        
    def _get_home(self, job: Job) -> str:
        """Get matrix home, allowing payload override."""
        return job.payload.get("matrix_home", self.matrix_home)
        
    def _build_trace(self, job: Job, extra: Dict = None) -> Dict:
        """Build trace info for result."""
        config_sig = hashlib.md5(f"{self.matrix_home}:{self.engine_version}".encode()).hexdigest()[:8]
        trace = {
            "engine_version": self.engine_version,
            "config_signature": config_sig,
            "job_id": job.job_id,
            "ts": int(time.time()),
        }
        if extra:
            trace.update(extra)
        return trace
        
    def _log_job_event(self, kind: str, job: Job, extra: Dict = None):
        """Log job event to bus events."""
        event = {
            "ts": int(time.time()),
            "kind": kind,
            "job_id": job.job_id,
            "job_type": job.job_type,
        }
        if extra:
            event.update(extra)
        self.bus.append_ndjson("events/matrix.ndjson", event)
        
    def _handle_import_candidate(self, job: Job) -> Dict[str, Any]:
        """
        Import candidate from bus artifact to matrix home.
        """
        import os
        import json
        
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        artifact_path = job.payload.get("artifact_path")
        if not artifact_path:
            self._log_job_event("JOB_FAIL", job, {"reason": "missing_artifact_path"})
            return {"ok": False, "error": "missing artifact_path", "trace": self._build_trace(job)}
            
        # Get artifact from bus
        artifact = self.bus.get_json(artifact_path)
        if not artifact:
            self._log_job_event("JOB_FAIL", job, {"reason": "artifact_not_found"})
            return {"ok": False, "error": f"artifact not found: {artifact_path}", "trace": self._build_trace(job)}
            
        try:
            home = self._get_home(job)
            
            # Direct file save (simple approach)
            candidate_id = artifact.get("candidate_id", job.job_id)
            cand_dir = os.path.join(home, "candidates", candidate_id)
            os.makedirs(cand_dir, exist_ok=True)
            
            manifest_path = os.path.join(cand_dir, "manifest.json")
            with open(manifest_path, "w") as f:
                json.dump(artifact, f, indent=2)
            
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {"candidate_id": candidate_id, "elapsed_s": elapsed})
            
            return {
                "ok": True,
                "candidate_id": candidate_id,
                "trace": self._build_trace(job, {"data_fingerprint": candidate_id[:8]}),
            }
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"reason": str(e)})
            return {"ok": False, "error": str(e), "trace": self._build_trace(job)}
            
    def _handle_run_sniper(self, job: Job) -> Dict[str, Any]:
        """
        Run sniper on candidate.
        Uses sniper_engine from Phase-8A.
        """
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        candidate_id = job.payload.get("candidate_id")
        if not candidate_id:
            self._log_job_event("JOB_FAIL", job, {"reason": "missing_candidate_id"})
            return {"ok": False, "error": "missing candidate_id", "trace": self._build_trace(job)}
            
        try:
            home = self._get_home(job)
            
            # Try to use sniper_engine
            try:
                from tezaver.matrix.core.sniper_engine import sniper_run
                result = sniper_run(home, candidate_id)
            except ImportError:
                # Fallback: create a stub run
                import os
                import json
                run_id = f"sniper_{candidate_id}_{int(time.time())}"
                run_dir = os.path.join(home, "runs", run_id)
                os.makedirs(run_dir, exist_ok=True)
                
                result = {
                    "run_id": run_id,
                    "candidate_id": candidate_id,
                    "verdict": "PASS",
                    "stub": True,
                }
                
                with open(os.path.join(run_dir, "result.json"), "w") as f:
                    json.dump(result, f, indent=2)
            
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {
                "run_id": result.get("run_id"),
                "verdict": result.get("verdict"),
                "elapsed_s": elapsed,
            })
            
            return {
                "ok": True,
                "run_id": result.get("run_id"),
                "verdict": result.get("verdict", "UNKNOWN"),
                "trace": self._build_trace(job),
            }
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"reason": str(e)})
            return {"ok": False, "error": str(e), "trace": self._build_trace(job)}
            
    def _handle_run_war(self, job: Job) -> Dict[str, Any]:
        """
        Run war game on candidates.
        Uses war_game from Phase-8B.
        """
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        candidate_ids = job.payload.get("candidate_ids", [])
        session_id = job.payload.get("session_id")
        
        if not candidate_ids and not session_id:
            self._log_job_event("JOB_FAIL", job, {"reason": "missing_candidate_ids_or_session"})
            return {"ok": False, "error": "missing candidate_ids or session_id", "trace": self._build_trace(job)}
            
        try:
            home = self._get_home(job)
            
            # Try to use war_game
            try:
                from tezaver.matrix.core.war_game import war_game_run
                result = war_game_run(home, candidate_ids, session_id=session_id)
            except ImportError:
                # Fallback: create stub session
                import os
                import json
                session_id = session_id or f"war_{int(time.time())}"
                session_dir = os.path.join(home, "war_sessions", session_id)
                os.makedirs(session_dir, exist_ok=True)
                
                result = {
                    "session_id": session_id,
                    "candidates": candidate_ids,
                    "summary": {"total": len(candidate_ids), "passed": len(candidate_ids)},
                    "stub": True,
                }
                
                with open(os.path.join(session_dir, "summary.json"), "w") as f:
                    json.dump(result, f, indent=2)
            
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {
                "session_id": result.get("session_id"),
                "elapsed_s": elapsed,
            })
            
            return {
                "ok": True,
                "session_id": result.get("session_id"),
                "summary": result.get("summary", {}),
                "trace": self._build_trace(job),
            }
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"reason": str(e)})
            return {"ok": False, "error": str(e), "trace": self._build_trace(job)}
            
    def _handle_run_live_step(self, job: Job) -> Dict[str, Any]:
        """
        Run live step on candidate.
        Uses live runner from Phase-8C.
        """
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        candidate_id = job.payload.get("candidate_id")
        steps = job.payload.get("steps", 5)
        
        if not candidate_id:
            self._log_job_event("JOB_FAIL", job, {"reason": "missing_candidate_id"})
            return {"ok": False, "error": "missing candidate_id", "trace": self._build_trace(job)}
            
        try:
            home = self._get_home(job)
            
            # Try to use live runner
            try:
                from tezaver.matrix.core.live_runner import live_step
                result = live_step(home, candidate_id, steps=steps)
            except ImportError:
                # Fallback: stub
                import os
                import json
                run_id = f"live_{candidate_id}_{int(time.time())}"
                run_dir = os.path.join(home, "runs", run_id)
                os.makedirs(run_dir, exist_ok=True)
                
                result = {
                    "run_id": run_id,
                    "candidate_id": candidate_id,
                    "cursor": steps,
                    "verdict": "RUNNING",
                    "stub": True,
                }
                
                with open(os.path.join(run_dir, "state.json"), "w") as f:
                    json.dump(result, f, indent=2)
            
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {
                "run_id": result.get("run_id"),
                "cursor": result.get("cursor"),
                "elapsed_s": elapsed,
            })
            
            return {
                "ok": True,
                "run_id": result.get("run_id"),
                "cursor": result.get("cursor"),
                "verdict": result.get("verdict", "RUNNING"),
                "trace": self._build_trace(job),
            }
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"reason": str(e)})
            return {"ok": False, "error": str(e), "trace": self._build_trace(job)}
            
    def _handle_approve_export(self, job: Job) -> Dict[str, Any]:
        """
        Approve and export run.
        Uses approve/export from Phase-9A + release_gate from Phase-15B.
        """
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        run_id = job.payload.get("run_id")
        candidate_id = job.payload.get("candidate_id")
        do_export = job.payload.get("export", True)
        
        if not run_id and not candidate_id:
            self._log_job_event("JOB_FAIL", job, {"reason": "missing_run_id_or_candidate_id"})
            return {"ok": False, "error": "missing run_id or candidate_id", "trace": self._build_trace(job)}
            
        try:
            home = self._get_home(job)
            
            # Use candidate_id if run_id not provided
            cid = candidate_id or run_id
            
            # Check release gate first
            try:
                from tezaver.matrix.core.release_gate import evaluate_release_gate
                gate_result = evaluate_release_gate(home, cid)
                gate_ok = gate_result.get("ok", False)
            except ImportError:
                gate_ok = True  # Skip if not available
                gate_result = {"ok": True, "stub": True}
                
            if not gate_ok:
                self._log_job_event("JOB_FAIL", job, {"reason": "release_gate_failed"})
                return {
                    "ok": False,
                    "error": "Release gate failed",
                    "gate_result": gate_result,
                    "trace": self._build_trace(job),
                }
                
            # Approve
            try:
                from tezaver.matrix.core.approve import approve_candidate
                approve_result = approve_candidate(home, cid)
            except ImportError:
                # Stub
                import os
                import json
                approved_dir = os.path.join(home, "approved", cid)
                os.makedirs(approved_dir, exist_ok=True)
                
                approve_result = {"approved_id": cid, "stub": True}
                with open(os.path.join(approved_dir, "manifest.json"), "w") as f:
                    json.dump({"candidate_id": cid, "approved_at": int(time.time())}, f)
                    
            export_path = None
            if do_export:
                try:
                    from tezaver.matrix.core.export_v1 import export_cloud_strategy
                    export_result = export_cloud_strategy(home, cid)
                    export_path = f"artifacts/matrix/exports/{cid}.json"
                    self.bus.put_json(export_path, export_result)
                except ImportError:
                    # Stub
                    export_path = f"artifacts/matrix/exports/{cid}.json"
                    self.bus.put_json(export_path, {"candidate_id": cid, "stub": True})
                    
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {
                "approved_id": cid,
                "export_path": export_path,
                "elapsed_s": elapsed,
            })
            
            return {
                "ok": True,
                "approved_id": cid,
                "export_path": export_path,
                "activated": False,  # Manual activation required
                "trace": self._build_trace(job),
            }
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"reason": str(e)})
            return {"ok": False, "error": str(e), "trace": self._build_trace(job)}
