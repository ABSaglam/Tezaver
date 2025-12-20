import os
import json
from typing import List, Optional
from tezaver.matrix.ports.candidate_bundle import validate_bundle_dict, bundle_from_dict, candidate_id, bundle_to_dict

class FileCandidateStore:
    def __init__(self, home: Optional[str] = None):
        if not home:
            home = os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
        self.home = home
        
    def candidates_dir(self) -> str:
        return os.path.join(self.home, "candidates")
        
    def _ensure_dir(self):
        os.makedirs(self.candidates_dir(), exist_ok=True)
        
    def save(self, bundle_dict: dict) -> str:
        # 1. Validate
        errors = validate_bundle_dict(bundle_dict)
        if errors:
            raise ValueError(f"Invalid bundle: {'; '.join(errors)}")
            
        # 2. Convert to Obj to get ID (safe way)
        # Or if the dict is trusted we could just calc ID from dict members.
        # But let's roundtrip to be safe and use proper dataclass logic.
        try:
            obj = bundle_from_dict(bundle_dict)
        except ValueError as e:
            raise ValueError(f"Structure mismatch: {e}")
            
        cid = candidate_id(obj)
        
        # 3. Save
        self._ensure_dir()
        path = os.path.join(self.candidates_dir(), f"{cid}.json")
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bundle_dict, f, indent=2, ensure_ascii=False)
            
        return cid
        
    def load(self, candidate_id: str) -> dict:
        path = os.path.join(self.candidates_dir(), f"{candidate_id}.json")
        if not os.path.exists(path):
            raise FileNotFoundError(f"Candidate {candidate_id} not found")
            
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    def list_ids(self) -> List[str]:
        d = self.candidates_dir()
        if not os.path.exists(d):
            return []
            
        files = [f for f in os.listdir(d) if f.endswith(".json")]
        ids = [f[:-5] for f in files] # remove .json
        return sorted(ids)
