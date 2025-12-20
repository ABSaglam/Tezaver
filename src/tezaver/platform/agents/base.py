"""
MX-20003: Agent Kit

Base agent class with HTTP endpoints and job processing.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, Callable
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading

from tezaver.platform.bus.adapter import BusAdapter, FsBusAdapter, create_bus_adapter
from tezaver.platform.jobs.queue import (
    Job, claim_next_job, write_result, write_deadletter
)


@dataclass
class AgentConfig:
    """Agent configuration."""
    agent_name: str
    bus_root: str
    token: str
    host: str = "0.0.0.0"
    port: int = 9000
    
    
class BaseAgent(ABC):
    """Base agent with HTTP server and job processing."""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.bus = create_bus_adapter(config.bus_root)
        self._handlers: Dict[str, Callable[[Job], Dict]] = {}
        
    def register_handler(self, job_type: str, handler: Callable[[Job], Dict]) -> None:
        """Register a handler for a job type."""
        self._handlers[job_type] = handler
        
    def scan_inbox(self, max_jobs: int = 5) -> int:
        """Scan inbox and process jobs."""
        jobs = claim_next_job(self.bus, self.config.agent_name, max_n=max_jobs)
        processed = 0
        
        for job in jobs:
            try:
                handler = self._handlers.get(job.job_type)
                if handler:
                    result = handler(job)
                    write_result(self.bus, self.config.agent_name, job.job_id, result)
                    processed += 1
                else:
                    write_deadletter(
                        self.bus, 
                        self.config.agent_name, 
                        job.job_id, 
                        f"No handler for job type: {job.job_type}"
                    )
            except Exception as e:
                write_deadletter(
                    self.bus, 
                    self.config.agent_name, 
                    job.job_id, 
                    str(e)
                )
                
        return processed
        
    def tick(self) -> Dict[str, Any]:
        """Single tick: scan inbox and return status."""
        processed = self.scan_inbox()
        return {
            "agent": self.config.agent_name,
            "processed": processed,
            "status": "ok",
        }
        
    def health(self) -> Dict[str, Any]:
        """Return health status."""
        return {
            "agent": self.config.agent_name,
            "status": "healthy",
            "bus_root": self.config.bus_root,
            "bus_type": self.bus.bus_type,
        }
        
    @abstractmethod
    def setup_handlers(self) -> None:
        """Setup job handlers. Must be implemented by subclass."""
        pass


class AgentHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for agent endpoints."""
    
    agent: Optional[BaseAgent] = None
    token: str = ""
    
    def _check_token(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:] == self.token
        return self.token == ""  # Allow if no token configured
        
    def _json_response(self, data: Dict, status: int = 200):
        self.send_response(status)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
        
    def do_GET(self):
        if self.path == "/health":
            if self.agent:
                self._json_response(self.agent.health())
            else:
                self._json_response({"status": "no agent"}, 500)
        else:
            self._json_response({"error": "not found"}, 404)
            
    def do_POST(self):
        if not self._check_token():
            self._json_response({"error": "unauthorized"}, 401)
            return
            
        if self.path == "/control/scan_inbox":
            if self.agent:
                processed = self.agent.scan_inbox()
                self._json_response({"processed": processed})
            else:
                self._json_response({"error": "no agent"}, 500)
                
        elif self.path == "/control/tick":
            if self.agent:
                result = self.agent.tick()
                self._json_response(result)
            else:
                self._json_response({"error": "no agent"}, 500)
        else:
            self._json_response({"error": "not found"}, 404)
            
    def log_message(self, format, *args):
        pass  # Suppress logging


def run_agent_server(agent: BaseAgent) -> None:
    """Run agent HTTP server (blocking)."""
    agent.setup_handlers()
    
    # Create handler class with agent reference
    handler = type("Handler", (AgentHTTPHandler,), {
        "agent": agent,
        "token": agent.config.token,
    })
    
    server = HTTPServer((agent.config.host, agent.config.port), handler)
    print(f"Agent {agent.config.agent_name} running on port {agent.config.port}")
    server.serve_forever()
    
    
def run_agent_server_thread(agent: BaseAgent) -> threading.Thread:
    """Run agent HTTP server in background thread."""
    thread = threading.Thread(target=run_agent_server, args=(agent,), daemon=True)
    thread.start()
    return thread
