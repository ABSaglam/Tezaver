"""
MX-21006..21007: Matrix Agent - Real Binding (No Stub)

Handles Matrix engine jobs with real V4 core/apps calls.
Stub fallback is disabled by default (allow_stubs=False).
"""

import time
import hashlib
from typing import Dict, Any
from dataclasses import dataclass, field

from tezaver.platform.agents.base import BaseAgent, AgentConfig
from tezaver.platform.jobs.queue import Job


class MissingBindingError(Exception):
    """Raised when a required binding is not available."""
    def __init__(self, code: str, detail: str, detail_tr: str = ""):
        self.code = code
        self.detail = detail
        self.detail_tr = detail_tr or detail
        super().__init__(f"{code}: {detail}")


@dataclass
class MatrixAgentConfig(AgentConfig):
    """Extended config for Matrix Agent."""
    matrix_home: str = ".tezaver_matrix"
    max_attempts: int = 3
    engine_version: str = "v4.0"
    allow_stubs: bool = False  # MX-21006: No stub by default


class MatrixAgent(BaseAgent):
    """Matrix engine agent with real V4 bindings."""
    
    def __init__(self, config: MatrixAgentConfig):
        super().__init__(config)
        self.matrix_home = config.matrix_home
        self.max_attempts = config.max_attempts
        self.engine_version = config.engine_version
        self.allow_stubs = config.allow_stubs
        
    def setup_handlers(self) -> None:
        self.register_handler("MATRIX_IMPORT_CANDIDATE", self._handle_import_candidate)
        self.register_handler("MATRIX_RUN_SNIPER", self._handle_run_sniper)
        self.register_handler("MATRIX_RUN_WAR", self._handle_run_war)
        self.register_handler("MATRIX_RUN_LIVE_STEP", self._handle_run_live_step)
        self.register_handler("MATRIX_APPROVE_EXPORT", self._handle_approve_export)
        self.register_handler("MATRIX_RELEASE_CHECK", self._handle_release_check)
        self.register_handler("MATRIX_REHEARSAL_CHECK", self._handle_rehearsal_check)
        
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
        """Import candidate from bus artifact to matrix home."""
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        artifact_path = job.payload.get("artifact_path")
        if not artifact_path:
            self._log_job_event("JOB_FAIL", job, {"error_code": "MISSING_ARTIFACT_PATH"})
            return {
                "ok": False, 
                "error_code": "MISSING_ARTIFACT_PATH",
                "error_detail_tr": "artifact_path parametresi eksik",
                "trace": self._build_trace(job),
            }
            
        artifact = self.bus.get_json(artifact_path)
        if not artifact:
            self._log_job_event("JOB_FAIL", job, {"error_code": "ARTIFACT_NOT_FOUND"})
            return {
                "ok": False, 
                "error_code": "ARTIFACT_NOT_FOUND",
                "error_detail_tr": f"Artifact bulunamadı: {artifact_path}",
                "trace": self._build_trace(job),
            }
            
        try:
            home = self._get_home(job)
            
            # Use real binding
            from tezaver.matrix.apps.platform_bindings import import_candidate
            result = import_candidate(home, artifact)
            
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {
                "candidate_id": result.get("candidate_id"),
                "elapsed_s": elapsed,
            })
            
            return {
                "ok": True,
                "candidate_id": result.get("candidate_id"),
                "trace": self._build_trace(job, {"data_fingerprint": result.get("candidate_id", "")[:8]}),
            }
        except ImportError as e:
            if self.allow_stubs:
                # Stub fallback (only if allowed)
                return self._stub_import(job, artifact)
            raise MissingBindingError(
                "BINDING_MISSING",
                f"import_candidate binding not available: {e}",
                "import_candidate bağlantısı bulunamadı"
            )
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"error_code": "EXCEPTION", "detail": str(e)})
            return {
                "ok": False, 
                "error_code": "EXCEPTION",
                "error_detail_tr": str(e),
                "trace": self._build_trace(job),
            }
            
    def _handle_run_sniper(self, job: Job) -> Dict[str, Any]:
        """Run sniper on candidate."""
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        candidate_id = job.payload.get("candidate_id")
        if not candidate_id:
            self._log_job_event("JOB_FAIL", job, {"error_code": "MISSING_CANDIDATE_ID"})
            return {
                "ok": False, 
                "error_code": "MISSING_CANDIDATE_ID",
                "error_detail_tr": "candidate_id parametresi eksik",
                "trace": self._build_trace(job),
            }
            
        try:
            home = self._get_home(job)
            
            # Use real binding
            from tezaver.matrix.apps.platform_bindings import run_sniper
            result = run_sniper(home, candidate_id)
            
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {
                "run_id": result.get("run_id"),
                "verdict": result.get("verdict"),
                "elapsed_s": elapsed,
            })
            
            return {
                "ok": True,
                "run_id": result.get("run_id"),
                "verdict": result.get("verdict"),
                "scorecard_path": result.get("scorecard_path"),
                "judge_path": result.get("judge_path"),
                "trace": self._build_trace(job),
            }
        except ImportError as e:
            if self.allow_stubs:
                return self._stub_sniper(job, candidate_id)
            raise MissingBindingError(
                "BINDING_MISSING",
                f"run_sniper binding not available: {e}",
                "run_sniper bağlantısı bulunamadı"
            )
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"error_code": "EXCEPTION", "detail": str(e)})
            return {
                "ok": False, 
                "error_code": "EXCEPTION",
                "error_detail_tr": str(e),
                "trace": self._build_trace(job),
            }
            
    def _handle_run_war(self, job: Job) -> Dict[str, Any]:
        """Run war game on candidates."""
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        candidate_ids = job.payload.get("candidate_ids", [])
        session_id = job.payload.get("session_id")
        
        if not candidate_ids and not session_id:
            self._log_job_event("JOB_FAIL", job, {"error_code": "MISSING_PARAMS"})
            return {
                "ok": False, 
                "error_code": "MISSING_PARAMS",
                "error_detail_tr": "candidate_ids veya session_id gerekli",
                "trace": self._build_trace(job),
            }
            
        try:
            home = self._get_home(job)
            
            from tezaver.matrix.apps.platform_bindings import run_war
            result = run_war(home, candidate_ids, session_id)
            
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {
                "session_id": result.get("session_id"),
                "elapsed_s": elapsed,
            })
            
            return {
                "ok": True,
                "session_id": result.get("session_id"),
                "pass_count": result.get("pass_count"),
                "fail_count": result.get("fail_count"),
                "trace": self._build_trace(job),
            }
        except ImportError as e:
            if self.allow_stubs:
                return {"ok": True, "session_id": "stub", "stub": True}
            raise MissingBindingError("BINDING_MISSING", str(e))
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"error_code": "EXCEPTION", "detail": str(e)})
            return {"ok": False, "error_code": "EXCEPTION", "error_detail_tr": str(e), "trace": self._build_trace(job)}
            
    def _handle_run_live_step(self, job: Job) -> Dict[str, Any]:
        """Run live step on candidate."""
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        candidate_id = job.payload.get("candidate_id")
        steps = job.payload.get("steps", 5)
        
        if not candidate_id:
            return {"ok": False, "error_code": "MISSING_CANDIDATE_ID", "trace": self._build_trace(job)}
            
        try:
            home = self._get_home(job)
            
            from tezaver.matrix.apps.platform_bindings import run_live_step
            result = run_live_step(home, candidate_id, steps)
            
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {"run_id": result.get("run_id"), "elapsed_s": elapsed})
            
            return {
                "ok": True,
                "run_id": result.get("run_id"),
                "cursor": result.get("cursor"),
                "verdict": result.get("verdict"),
                "trace": self._build_trace(job),
            }
        except ImportError as e:
            if self.allow_stubs:
                return {"ok": True, "run_id": "stub", "cursor": steps, "verdict": "RUNNING", "stub": True}
            raise MissingBindingError("BINDING_MISSING", str(e))
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"error_code": "EXCEPTION", "detail": str(e)})
            return {"ok": False, "error_code": "EXCEPTION", "error_detail_tr": str(e), "trace": self._build_trace(job)}
            
    def _handle_approve_export(self, job: Job) -> Dict[str, Any]:
        """Approve and export candidate."""
        self._log_job_event("JOB_START", job)
        start_ts = time.time()
        
        run_id = job.payload.get("run_id")
        candidate_id = job.payload.get("candidate_id")
        do_export = job.payload.get("export", True)
        
        cid = candidate_id or run_id
        if not cid:
            return {"ok": False, "error_code": "MISSING_ID", "trace": self._build_trace(job)}
            
        try:
            home = self._get_home(job)
            
            from tezaver.matrix.apps.platform_bindings import approve_export
            result = approve_export(home, cid, do_export)
            
            # Also put export to bus if path exists
            if result.get("export_path"):
                import json
                with open(result["export_path"]) as f:
                    export_data = json.load(f)
                bus_path = f"artifacts/matrix/exports/{cid}.json"
                self.bus.put_json(bus_path, export_data)
                result["bus_export_path"] = bus_path
            
            elapsed = time.time() - start_ts
            self._log_job_event("JOB_OK", job, {"approved_id": cid, "elapsed_s": elapsed})
            
            return {
                "ok": True,
                "approved_id": result.get("approved_id"),
                "export_path": result.get("export_path"),
                "bus_export_path": result.get("bus_export_path"),
                "trace": self._build_trace(job),
            }
        except ImportError as e:
            if self.allow_stubs:
                return {"ok": True, "approved_id": cid, "stub": True}
            raise MissingBindingError("BINDING_MISSING", str(e))
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"error_code": "EXCEPTION", "detail": str(e)})
            return {"ok": False, "error_code": "EXCEPTION", "error_detail_tr": str(e), "trace": self._build_trace(job)}
            
    def _handle_release_check(self, job: Job) -> Dict[str, Any]:
        """Check release gate for candidate."""
        self._log_job_event("JOB_START", job)
        
        candidate_id = job.payload.get("candidate_id")
        context = job.payload.get("context", {})
        
        if not candidate_id:
            return {"ok": False, "error_code": "MISSING_CANDIDATE_ID", "trace": self._build_trace(job)}
            
        try:
            home = self._get_home(job)
            
            from tezaver.matrix.apps.platform_bindings import release_check
            result = release_check(home, candidate_id, context)
            
            self._log_job_event("JOB_OK", job, {
                "release_status": result.get("release_status"),
                "candidate_id": candidate_id,
            })
            
            return {
                "ok": True,
                "release_status": result.get("release_status"),
                "fail_codes": result.get("fail_codes", []),
                "details_tr": result.get("details_tr", []),
                "candidate_id": candidate_id,
                "trace": self._build_trace(job),
            }
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"error_code": "EXCEPTION", "detail": str(e)})
            return {"ok": False, "error_code": "EXCEPTION", "error_detail_tr": str(e), "trace": self._build_trace(job)}
            
    def _handle_rehearsal_check(self, job: Job) -> Dict[str, Any]:
        """Check rehearsal (go/no-go) for candidate."""
        self._log_job_event("JOB_START", job)
        
        candidate_id = job.payload.get("candidate_id")
        mode = job.payload.get("mode", "PAPER")
        
        if not candidate_id:
            return {"ok": False, "error_code": "MISSING_CANDIDATE_ID", "trace": self._build_trace(job)}
            
        try:
            home = self._get_home(job)
            
            from tezaver.matrix.apps.platform_bindings import rehearsal_check
            result = rehearsal_check(home, candidate_id, mode)
            
            self._log_job_event("JOB_OK", job, {
                "rehearsal": result.get("rehearsal"),
                "candidate_id": candidate_id,
            })
            
            return {
                "ok": True,
                "rehearsal": result.get("rehearsal"),
                "fail_codes": result.get("fail_codes", []),
                "details_tr": result.get("details_tr", []),
                "candidate_id": candidate_id,
                "mode": mode,
                "trace": self._build_trace(job),
            }
        except Exception as e:
            self._log_job_event("JOB_FAIL", job, {"error_code": "EXCEPTION", "detail": str(e)})
            return {"ok": False, "error_code": "EXCEPTION", "error_detail_tr": str(e), "trace": self._build_trace(job)}
            
    # Stub methods (only used if allow_stubs=True)
    def _stub_import(self, job: Job, artifact: Dict) -> Dict:
        import os, json
        home = self._get_home(job)
        cid = artifact.get("candidate_id", job.job_id)
        cand_dir = os.path.join(home, "candidates", cid)
        os.makedirs(cand_dir, exist_ok=True)
        with open(os.path.join(cand_dir, "manifest.json"), "w") as f:
            json.dump(artifact, f)
        return {"ok": True, "candidate_id": cid, "stub": True, "trace": self._build_trace(job)}
        
    def _stub_sniper(self, job: Job, candidate_id: str) -> Dict:
        import os, json
        home = self._get_home(job)
        run_id = f"sniper_{candidate_id}_{int(time.time())}"
        run_dir = os.path.join(home, "runs", run_id)
        os.makedirs(run_dir, exist_ok=True)
        with open(os.path.join(run_dir, "result.json"), "w") as f:
            json.dump({"run_id": run_id, "verdict": "PASS", "stub": True}, f)
        return {"ok": True, "run_id": run_id, "verdict": "PASS", "stub": True, "trace": self._build_trace(job)}
