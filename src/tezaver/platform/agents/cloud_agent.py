"""
MX-21009: Cloud Agent - Real Import/Tick/Pause/Resume

Handles Cloud engine jobs with real bindings.
"""

import os
import json
import time
from typing import Dict, Any
from dataclasses import dataclass

from tezaver.platform.agents.base import BaseAgent, AgentConfig
from tezaver.platform.jobs.queue import Job


@dataclass
class CloudAgentConfig(AgentConfig):
    """Extended config for Cloud Agent."""
    cloud_home: str = ".tezaver_matrix"
    allow_stubs: bool = False


class CloudAgent(BaseAgent):
    """Cloud engine agent with real bindings."""
    
    def __init__(self, config: CloudAgentConfig):
        super().__init__(config)
        self.cloud_home = config.cloud_home
        self.allow_stubs = config.allow_stubs
        
    def setup_handlers(self) -> None:
        self.register_handler("CLOUD_IMPORT_STRATEGY", self._handle_import_strategy)
        self.register_handler("CLOUD_SET_STATUS", self._handle_set_status)
        self.register_handler("CLOUD_RUNTIME_TICK", self._handle_runtime_tick)
        self.register_handler("CLOUD_PAUSE", self._handle_pause)
        self.register_handler("CLOUD_RESUME", self._handle_resume)
        
    def _get_home(self, job: Job) -> str:
        return job.payload.get("cloud_home", self.cloud_home)
        
    def _log_event(self, kind: str, job: Job, extra: Dict = None):
        event = {
            "ts": int(time.time()),
            "kind": kind,
            "job_id": job.job_id,
            "job_type": job.job_type,
        }
        if extra:
            event.update(extra)
        self.bus.append_event("cloud", event)
        
    def _handle_import_strategy(self, job: Job) -> Dict[str, Any]:
        """Import strategy from export artifact."""
        self._log_event("JOB_START", job)
        
        export_path = job.payload.get("export_path")
        if not export_path:
            return {"ok": False, "error_code": "MISSING_EXPORT_PATH"}
            
        # Get from bus
        export_data = self.bus.get_json(export_path)
        if not export_data:
            return {"ok": False, "error_code": "EXPORT_NOT_FOUND", "detail": export_path}
            
        try:
            home = self._get_home(job)
            
            # Register in cloud registry
            strategy_id = export_data.get("candidate_id") or export_data.get("export_id")
            if not strategy_id:
                strategy_id = f"STRAT_{int(time.time())}"
                
            strat_dir = os.path.join(home, "cloud_registry", "strategies", strategy_id)
            os.makedirs(strat_dir, exist_ok=True)
            
            strategy = {
                "strategy_id": strategy_id,
                "symbol": export_data.get("symbol"),
                "timeframe": export_data.get("timeframe"),
                "params": export_data.get("params", {}),
                "status_info": {"status": "PAUSED"},
                "imported_at": int(time.time()),
                "source_export": export_path,
            }
            
            with open(os.path.join(strat_dir, "strategy.json"), "w") as f:
                json.dump(strategy, f, indent=2)
                
            self._log_event("JOB_OK", job, {"strategy_id": strategy_id})
            
            return {"ok": True, "strategy_id": strategy_id, "status": "PAUSED"}
        except Exception as e:
            self._log_event("JOB_FAIL", job, {"detail": str(e)})
            return {"ok": False, "error_code": "EXCEPTION", "detail": str(e)}
            
    def _handle_set_status(self, job: Job) -> Dict[str, Any]:
        """Set strategy status (ACTIVE/PAUSED)."""
        self._log_event("JOB_START", job)
        
        strategy_id = job.payload.get("strategy_id")
        status = job.payload.get("status", "PAUSED")
        
        if not strategy_id:
            return {"ok": False, "error_code": "MISSING_STRATEGY_ID"}
            
        try:
            home = self._get_home(job)
            strat_path = os.path.join(home, "cloud_registry", "strategies", strategy_id, "strategy.json")
            
            if not os.path.exists(strat_path):
                return {"ok": False, "error_code": "STRATEGY_NOT_FOUND"}
                
            with open(strat_path) as f:
                strategy = json.load(f)
                
            strategy["status_info"]["status"] = status
            strategy["status_updated_at"] = int(time.time())
            
            with open(strat_path, "w") as f:
                json.dump(strategy, f, indent=2)
                
            self._log_event("JOB_OK", job, {"strategy_id": strategy_id, "status": status})
            
            return {"ok": True, "strategy_id": strategy_id, "status": status}
        except Exception as e:
            return {"ok": False, "error_code": "EXCEPTION", "detail": str(e)}
            
    def _handle_runtime_tick(self, job: Job) -> Dict[str, Any]:
        """Execute runtime tick."""
        self._log_event("JOB_START", job)
        
        ticks = job.payload.get("ticks", 1)
        home = self._get_home(job)
        
        try:
            # Write tick events
            events_written = 0
            for i in range(ticks):
                self.bus.append_event("cloud", {
                    "ts": int(time.time()),
                    "kind": "RUNTIME_TICK",
                    "tick_num": i + 1,
                    "job_id": job.job_id,
                })
                events_written += 1
                
            # Also write to cloud_runtime state
            state_path = os.path.join(home, "cloud_runtime", "state.json")
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            
            state = {}
            if os.path.exists(state_path):
                with open(state_path) as f:
                    state = json.load(f)
                    
            state["last_tick_at"] = int(time.time())
            state["total_ticks"] = state.get("total_ticks", 0) + ticks
            
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)
                
            self._log_event("JOB_OK", job, {"ticks_done": ticks, "events_written": events_written})
            
            return {"ok": True, "ticks_done": ticks, "events_written": events_written}
        except Exception as e:
            return {"ok": False, "error_code": "EXCEPTION", "detail": str(e)}
            
    def _handle_pause(self, job: Job) -> Dict[str, Any]:
        """Pause cloud runtime (kill switch)."""
        self._log_event("JOB_START", job)
        
        try:
            home = self._get_home(job)
            gr_path = os.path.join(home, "cloud_runtime", "global_risk.json")
            os.makedirs(os.path.dirname(gr_path), exist_ok=True)
            
            gr = {}
            if os.path.exists(gr_path):
                with open(gr_path) as f:
                    gr = json.load(f)
                    
            gr["paused"] = True
            gr["paused_at"] = int(time.time())
            
            with open(gr_path, "w") as f:
                json.dump(gr, f, indent=2)
                
            self._log_event("JOB_OK", job, {"paused": True})
            
            return {"ok": True, "paused": True}
        except Exception as e:
            return {"ok": False, "error_code": "EXCEPTION", "detail": str(e)}
            
    def _handle_resume(self, job: Job) -> Dict[str, Any]:
        """Resume cloud runtime."""
        self._log_event("JOB_START", job)
        
        try:
            home = self._get_home(job)
            gr_path = os.path.join(home, "cloud_runtime", "global_risk.json")
            os.makedirs(os.path.dirname(gr_path), exist_ok=True)
            
            gr = {}
            if os.path.exists(gr_path):
                with open(gr_path) as f:
                    gr = json.load(f)
                    
            gr["paused"] = False
            gr["resumed_at"] = int(time.time())
            
            with open(gr_path, "w") as f:
                json.dump(gr, f, indent=2)
                
            self._log_event("JOB_OK", job, {"paused": False})
            
            return {"ok": True, "paused": False}
        except Exception as e:
            return {"ok": False, "error_code": "EXCEPTION", "detail": str(e)}
