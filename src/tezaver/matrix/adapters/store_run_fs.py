import os
import json
from typing import Dict, List
from tezaver.matrix.ports.store_port import StorePort

class FileRunStore(StorePort):
    def __init__(self, home: str = None):
        if not home:
            home = os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
        self.home = home
        
    def _run_dir(self, run_id: str) -> str:
        d = os.path.join(self.home, "runs", run_id)
        os.makedirs(d, exist_ok=True)
        return d

    def create_run(self, run_id: str, meta: Dict) -> None:
        d = self._run_dir(run_id)
        path = os.path.join(d, "meta.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    def append_event(self, run_id: str, event: Dict) -> None:
        d = self._run_dir(run_id)
        path = os.path.join(d, "events.ndjson")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

    def write_gates(self, run_id: str, gates: Dict) -> None:
        d = self._run_dir(run_id)
        path = os.path.join(d, "gates.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(gates, f, indent=2)

    def write_audit(self, run_id: str, audit: Dict) -> None:
        d = self._run_dir(run_id)
        path = os.path.join(d, "audit.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(audit, f, indent=2)

    def finalize_run(self, run_id: str) -> None:
        # No-op for FS store currently
        pass

    def list_incidents(self) -> List[str]:
        d = os.path.join(self.home, "incidents")
        if not os.path.exists(d):
            return []
        # Return sorted list of incident IDs
        incidents = [
            dname for dname in os.listdir(d) 
            if os.path.isdir(os.path.join(d, dname)) and dname.startswith("INC_")
        ]
        incidents.sort(reverse=True)
        return incidents

    def read_incident_manifest(self, incident_id: str) -> Dict:
        path = os.path.join(self.home, "incidents", incident_id, "manifest.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
