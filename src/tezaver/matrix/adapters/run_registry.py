import json
import os
from typing import List, Dict, Optional
from datetime import datetime

class RunRegistry:
    """
    MXI-1160: Persistent store for Matrix runs and results.
    """
    def __init__(self, registry_path: str = "data/matrix/runs_registry.jsonl"):
        self.registry_path = registry_path
        self._ensure_dir()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)

    def register_run(self, run_id: str, candidate_id: str, symbol: str, tf: str, scorecard: dict, verdict: str):
        entry = {
            "run_id": run_id,
            "candidate_id": candidate_id,
            "symbol": symbol,
            "tf": tf,
            "verdict": verdict,
            "trades_count": scorecard.get("trades_count", 0),
            "pnl": scorecard.get("total_pnl_raw", 0), # Placeholder for real pnl
            "created_at": datetime.now().isoformat()
        }
        with open(self.registry_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def list_all(self) -> List[Dict]:
        if not os.path.exists(self.registry_path):
            return []
        runs = []
        with open(self.registry_path, "r") as f:
            for line in f:
                if line.strip():
                    runs.append(json.loads(line))
        return runs

    def get(self, run_id: str) -> Optional[Dict]:
        all_runs = self.list_all()
        for r in all_runs:
            if r["run_id"] == run_id:
                return r
        return None
