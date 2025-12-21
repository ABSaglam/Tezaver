import os
import json
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

class CandidateRegistry:
    """
    MXI-1020: Registry for candidate status and metadata.
    TR: Aday durumları ve metadataları için kayıt defteri.
    """
    def __init__(self, registry_path: str = "data/matrix/candidates_registry.jsonl"):
        self.path = Path(registry_path)
        self._ensure_dir()
        self.candidates = self._load_all()

    def _ensure_dir(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.touch()

    def _load_all(self) -> Dict[str, Dict]:
        data = {}
        if not self.path.exists():
            return data
        with open(self.path, "r") as f:
            for line in f:
                if not line.strip(): continue
                entry = json.loads(line)
                data[entry['candidate_id']] = entry
        return data

    def register(self, 
                 candidate_id: str, 
                 symbol: str, 
                 tf: str, 
                 bundle_id: str, 
                 bundle_path: str,
                 metrics: Dict,
                 status: str = "NEW"):
        
        entry = {
            "candidate_id": candidate_id,
            "symbol": symbol,
            "tf": tf,
            "bundle_id": bundle_id,
            "bundle_path": bundle_path,
            "resolve_rate": metrics.get("trigger_resolve_rate", 0),
            "join_coverage": metrics.get("join_coverage", 0),
            "status": status,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        self.candidates[candidate_id] = entry
        self._save_all()
        return entry

    def update_status(self, candidate_id: str, status: str):
        if candidate_id in self.candidates:
            self.candidates[candidate_id]['status'] = status
            self.candidates[candidate_id]['updated_at'] = datetime.now().isoformat()
            self._save_all()

    def _save_all(self):
        with open(self.path, "w") as f:
            for entry in self.candidates.values():
                f.write(json.dumps(entry) + "\n")

    def list_all(self) -> List[Dict]:
        return list(self.candidates.values())

    def get(self, candidate_id: str) -> Optional[Dict]:
        return self.candidates.get(candidate_id)
