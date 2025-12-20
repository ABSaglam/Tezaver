"""
MX-21008: Mac Agent - Publish Artifacts

Handles Mac engine jobs: publish candidate/story to bus.
"""

import os
import json
import time
from typing import Dict, Any

from tezaver.platform.agents.base import BaseAgent, AgentConfig
from tezaver.platform.jobs.queue import Job


class MacAgent(BaseAgent):
    """Mac engine agent for publishing artifacts."""
    
    def setup_handlers(self) -> None:
        self.register_handler("MAC_BUILD_CANDIDATE", self._handle_build_candidate)
        self.register_handler("MAC_PUBLISH_CANDIDATE", self._handle_publish_candidate)
        self.register_handler("MAC_PUBLISH_STORY", self._handle_publish_story)
        
    def _handle_build_candidate(self, job: Job) -> Dict[str, Any]:
        """Build candidate from signals (legacy, generates in-bus artifact)."""
        symbol = job.payload.get("symbol", "BTCUSDT")
        timeframe = job.payload.get("timeframe", "15m")
        
        candidate = {
            "candidate_id": f"{symbol}_{timeframe}_{int(time.time())}",
            "symbol": symbol,
            "timeframe": timeframe,
            "build_ts": int(time.time()),
            "builder": "mac_agent",
            "signals": job.payload.get("signals", []),
            "params": job.payload.get("params", {}),
        }
        
        artifact_path = f"artifacts/mac/candidates/{candidate['candidate_id']}.json"
        self.bus.put_json(artifact_path, candidate)
        
        self.bus.append_ndjson("events/mac.ndjson", {
            "ts": int(time.time()),
            "kind": "CANDIDATE_BUILT",
            "candidate_id": candidate["candidate_id"],
            "job_id": job.job_id,
        })
        
        return {
            "ok": True,
            "candidate_id": candidate["candidate_id"],
            "artifact_path": artifact_path,
        }
        
    def _handle_publish_candidate(self, job: Job) -> Dict[str, Any]:
        """
        Publish candidate from local path to bus.
        
        Payload:
            local_path: Path to local JSON file
            artifact_path: Target path in bus
        """
        local_path = job.payload.get("local_path")
        artifact_path = job.payload.get("artifact_path")
        
        if not local_path:
            return {"ok": False, "error_code": "MISSING_LOCAL_PATH"}
        if not artifact_path:
            return {"ok": False, "error_code": "MISSING_ARTIFACT_PATH"}
            
        try:
            with open(local_path) as f:
                data = json.load(f)
                
            self.bus.put_json(artifact_path, data)
            
            self.bus.append_ndjson("events/mac.ndjson", {
                "ts": int(time.time()),
                "kind": "CANDIDATE_PUBLISHED",
                "artifact_path": artifact_path,
                "job_id": job.job_id,
            })
            
            return {"ok": True, "artifact_path": artifact_path}
        except FileNotFoundError:
            return {"ok": False, "error_code": "FILE_NOT_FOUND", "detail": local_path}
        except json.JSONDecodeError as e:
            return {"ok": False, "error_code": "INVALID_JSON", "detail": str(e)}
        except Exception as e:
            return {"ok": False, "error_code": "EXCEPTION", "detail": str(e)}
            
    def _handle_publish_story(self, job: Job) -> Dict[str, Any]:
        """Publish story from local path to bus."""
        local_path = job.payload.get("local_path")
        artifact_path = job.payload.get("artifact_path")
        
        if not local_path or not artifact_path:
            return {"ok": False, "error_code": "MISSING_PARAMS"}
            
        try:
            with open(local_path) as f:
                data = json.load(f)
                
            self.bus.put_json(artifact_path, data)
            
            self.bus.append_ndjson("events/mac.ndjson", {
                "ts": int(time.time()),
                "kind": "STORY_PUBLISHED",
                "artifact_path": artifact_path,
                "job_id": job.job_id,
            })
            
            return {"ok": True, "artifact_path": artifact_path}
        except Exception as e:
            return {"ok": False, "error_code": "EXCEPTION", "detail": str(e)}
