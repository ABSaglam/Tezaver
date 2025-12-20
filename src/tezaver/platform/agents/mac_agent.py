"""
MX-20005: Mac Agent

Handles Mac engine jobs: build candidate from signals.
"""

import time
from typing import Dict, Any
from tezaver.platform.agents.base import BaseAgent, AgentConfig
from tezaver.platform.jobs.queue import Job


class MacAgent(BaseAgent):
    """Mac engine agent."""
    
    def setup_handlers(self) -> None:
        self.register_handler("MAC_BUILD_CANDIDATE", self._handle_build_candidate)
        
    def _handle_build_candidate(self, job: Job) -> Dict[str, Any]:
        """Build candidate from signals."""
        symbol = job.payload.get("symbol", "BTCUSDT")
        timeframe = job.payload.get("timeframe", "15m")
        
        # Generate sample candidate
        candidate = {
            "candidate_id": f"{symbol}_{timeframe}_{int(time.time())}",
            "symbol": symbol,
            "timeframe": timeframe,
            "build_ts": int(time.time()),
            "builder": "mac_agent",
            "signals": job.payload.get("signals", []),
            "params": job.payload.get("params", {}),
        }
        
        # Write artifact to bus
        artifact_path = f"artifacts/mac/candidates/{candidate['candidate_id']}.json"
        self.bus.put_json(artifact_path, candidate)
        
        # Log event
        self.bus.append_ndjson("events/mac.ndjson", {
            "ts": int(time.time()),
            "kind": "CANDIDATE_BUILT",
            "candidate_id": candidate["candidate_id"],
        })
        
        return {
            "status": "built",
            "candidate_id": candidate["candidate_id"],
            "artifact_path": artifact_path,
        }
