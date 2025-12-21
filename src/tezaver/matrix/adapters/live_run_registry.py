"""
MX-3031: LiveRunRegistry - Registry for LIVE run state and history.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class LiveRunRegistry:
    """
    MX-3031: LiveRunRegistry
    Stores LIVE run metadata and heartbeat state in JSONL format.
    """
    
    def __init__(self, registry_path: str = "data/matrix/live_runs_registry.jsonl"):
        self.path = Path(registry_path)
        self._ensure_dir()
        self.runs = self._load_all()
    
    def _ensure_dir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()
    
    def _load_all(self) -> Dict[str, Dict]:
        """Load all runs keyed by run_id."""
        data = {}
        if not self.path.exists():
            return data
        with open(self.path, "r") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    data[entry["run_id"]] = entry
                except:
                    continue
        return data
    
    def register(
        self,
        run_id: str,
        plan_id: str,
        cells: List[Dict],
        symbols: List[str],
        config_hash: str,
        safe_mode: bool = False
    ) -> Dict:
        """Register a new LIVE run."""
        entry = {
            "run_id": run_id,
            "plan_id": plan_id,
            "cells": [{"symbol": c.symbol, "tf": c.tf, "candidate_id": c.candidate_id} for c in cells],
            "symbols": symbols,
            "config_hash": config_hash,
            "status": "RUNNING",
            "safe_mode": safe_mode,
            "started_at": datetime.now().isoformat(),
            "last_heartbeat_ts": datetime.now().isoformat(),
            "stopped_at": None,
            "bar_count": 0,
            "trade_count": 0,
            "incident_count": 0
        }
        
        self.runs[run_id] = entry
        self._save_all()
        return entry
    
    def update_heartbeat(self, run_id: str, bar_count: int = None, trade_count: int = None):
        """Update heartbeat timestamp."""
        if run_id in self.runs:
            self.runs[run_id]["last_heartbeat_ts"] = datetime.now().isoformat()
            if bar_count is not None:
                self.runs[run_id]["bar_count"] = bar_count
            if trade_count is not None:
                self.runs[run_id]["trade_count"] = trade_count
            self._save_all()
    
    def update_status(self, run_id: str, status: str):
        """Update run status (RUNNING, STOPPED, ERROR)."""
        if run_id in self.runs:
            self.runs[run_id]["status"] = status
            if status in ["STOPPED", "ERROR"]:
                self.runs[run_id]["stopped_at"] = datetime.now().isoformat()
            self._save_all()
    
    def increment_incident(self, run_id: str):
        """Increment incident count."""
        if run_id in self.runs:
            self.runs[run_id]["incident_count"] = self.runs[run_id].get("incident_count", 0) + 1
            self._save_all()
    
    def _save_all(self):
        with open(self.path, "w") as f:
            for entry in self.runs.values():
                f.write(json.dumps(entry) + "\n")
    
    def list_all(self) -> List[Dict]:
        return list(self.runs.values())
    
    def get(self, run_id: str) -> Optional[Dict]:
        return self.runs.get(run_id)
    
    def get_active_runs(self) -> List[Dict]:
        """Get currently running LIVE runs."""
        return [r for r in self.runs.values() if r.get("status") == "RUNNING"]
