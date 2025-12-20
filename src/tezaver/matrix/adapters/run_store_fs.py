import os
import json
from typing import List, Optional

class RunStoreFS:
    def __init__(self, home: Optional[str] = None):
        if not home:
            home = os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
        self.home = home
        
    def runs_dir(self) -> str:
        return os.path.join(self.home, "runs")
        
    def list_runs(self) -> List[str]:
        d = self.runs_dir()
        if not os.path.exists(d):
            return []
            
        runs = []
        for name in os.listdir(d):
            path = os.path.join(d, name)
            if os.path.isdir(path):
                runs.append(name)
        
        # Sort by creation time (folder name assumption or meta?)
        # For simple demo, sorting by name is likely OK if name has timestamp.
        # But let's try to sort by mtime or alphabetical reverse.
        runs.sort(reverse=True)
        return runs
        
    def load_meta(self, run_id: str) -> dict:
        path = os.path.join(self.runs_dir(), run_id, "meta.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    def read_gates(self, run_id: str) -> List[dict]:
        path = os.path.join(self.runs_dir(), run_id, "gates.json")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
            
    def read_events_head_tail(self, run_id: str, lines=20) -> str:
        path = os.path.join(self.runs_dir(), run_id, "events.ndjson")
        if not os.path.exists(path):
            return ""
            
        all_lines = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                all_lines.append(line.strip())
                
        if len(all_lines) <= lines * 2:
            return "\n".join(all_lines)
            
        head = all_lines[:lines]
        tail = all_lines[-lines:]
        return "\n".join(head) + "\n... (truncated) ...\n" + "\n".join(tail)
