"""
CLOUD-1030: CloudStateStore - State persistence for cloud service.
Handles run registry and reconciliation state.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class CloudStateStore:
    """
    CLOUD-1030: State persistence for cloud service.
    Stores run state and reconciliation data.
    """
    
    def __init__(self, data_dir: str = "data/cloud"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.runs_path = self.data_dir / "runs_registry.jsonl"
        self.state_path = self.data_dir / "live_state.json"
    
    # --- Run Registry ---
    
    def register_run(self, run_id: str, config: Dict) -> Dict:
        """Register a new cloud run."""
        entry = {
            "run_id": run_id,
            "started_at": datetime.now().isoformat(),
            "status": "RUNNING",
            "config": config,
            "bar_count": 0,
            "trade_count": 0,
            "last_heartbeat": datetime.now().isoformat()
        }
        
        self._append_run(entry)
        return entry
    
    def update_heartbeat(self, run_id: str, bar_count: int, trade_count: int):
        """Update run heartbeat."""
        runs = self._load_runs()
        for r in runs:
            if r["run_id"] == run_id:
                r["last_heartbeat"] = datetime.now().isoformat()
                r["bar_count"] = bar_count
                r["trade_count"] = trade_count
                break
        self._save_runs(runs)
    
    def update_status(self, run_id: str, status: str):
        """Update run status."""
        runs = self._load_runs()
        for r in runs:
            if r["run_id"] == run_id:
                r["status"] = status
                if status in ["STOPPED", "ERROR"]:
                    r["stopped_at"] = datetime.now().isoformat()
                break
        self._save_runs(runs)
    
    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get run by ID."""
        for r in self._load_runs():
            if r["run_id"] == run_id:
                return r
        return None
    
    def list_runs(self) -> List[Dict]:
        """List all runs."""
        return self._load_runs()
    
    def _append_run(self, entry: Dict):
        """Append run to registry."""
        with open(self.runs_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    
    def _load_runs(self) -> List[Dict]:
        """Load all runs."""
        if not self.runs_path.exists():
            return []
        runs = []
        with open(self.runs_path) as f:
            for line in f:
                if line.strip():
                    try:
                        runs.append(json.loads(line))
                    except:
                        pass
        return runs
    
    def _save_runs(self, runs: List[Dict]):
        """Save runs (rewrite all)."""
        with open(self.runs_path, "w") as f:
            for r in runs:
                f.write(json.dumps(r) + "\n")
    
    # --- Reconciliation State ---
    
    def save_state(self, run_id: str, positions: List[Dict], orders: List[Dict]):
        """Save reconciliation state."""
        state = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "open_positions": positions,
            "open_orders": orders
        }
        with open(self.state_path, "w") as f:
            json.dump(state, f, indent=2)
    
    def load_state(self) -> Optional[Dict]:
        """Load reconciliation state."""
        if not self.state_path.exists():
            return None
        try:
            with open(self.state_path) as f:
                return json.load(f)
        except:
            return None
    
    def clear_state(self):
        """Clear reconciliation state."""
        if self.state_path.exists():
            self.state_path.unlink()
    
    def check_reconciliation(self, run_id: str) -> Dict:
        """Check if state is consistent for restart."""
        state = self.load_state()
        
        if not state:
            return {"consistent": True, "safe_mode": False, "issues": []}
        
        issues = []
        safe_mode = False
        
        if state.get("open_positions"):
            issues.append(f"Found {len(state['open_positions'])} open positions")
            safe_mode = True
        
        if state.get("open_orders"):
            issues.append(f"Found {len(state['open_orders'])} open orders")
            safe_mode = True
        
        return {
            "consistent": len(issues) == 0,
            "safe_mode": safe_mode,
            "issues": issues,
            "previous_run_id": state.get("run_id")
        }
