"""
MX-2031: WarRunRegistry - Registry for WAR run results.
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class WarRunRegistry:
    """
    MX-2031: WarRunRegistry
    Stores WAR run metadata and results in JSONL format.
    """
    
    def __init__(self, registry_path: str = "data/matrix/war_runs_registry.jsonl"):
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
        candidate_ids: List[str],
        symbols: List[str],
        config_hash: str,
        scorecard: Dict = None,
        verdict: str = "PENDING"
    ) -> Dict:
        """Register a new WAR run."""
        entry = {
            "run_id": run_id,
            "plan_id": plan_id,
            "candidate_ids": candidate_ids,
            "symbols": symbols,
            "config_hash": config_hash,
            "verdict": verdict,
            "scorecard_summary": {
                "total_trades": scorecard.get("total_trades", 0) if scorecard else 0,
                "net_pnl": scorecard.get("net_pnl", 0) if scorecard else 0,
                "max_drawdown": scorecard.get("max_drawdown", 0) if scorecard else 0,
                "scorecard_hash": scorecard.get("scorecard_hash", "") if scorecard else ""
            },
            "started_at": datetime.now().isoformat(),
            "finished_at": None,
            "created_at": datetime.now().isoformat()
        }
        
        self.runs[run_id] = entry
        self._save_all()
        return entry
    
    def update_finished(self, run_id: str, scorecard: Dict, verdict: str):
        """Update run with final results."""
        if run_id in self.runs:
            self.runs[run_id]["finished_at"] = datetime.now().isoformat()
            self.runs[run_id]["verdict"] = verdict
            self.runs[run_id]["scorecard_summary"] = {
                "total_trades": scorecard.get("total_trades", 0),
                "net_pnl": scorecard.get("net_pnl", 0),
                "max_drawdown": scorecard.get("max_drawdown", 0),
                "scorecard_hash": scorecard.get("scorecard_hash", "")
            }
            self._save_all()
    
    def _save_all(self):
        with open(self.path, "w") as f:
            for entry in self.runs.values():
                f.write(json.dumps(entry) + "\n")
    
    def list_all(self) -> List[Dict]:
        return list(self.runs.values())
    
    def get(self, run_id: str) -> Optional[Dict]:
        return self.runs.get(run_id)
