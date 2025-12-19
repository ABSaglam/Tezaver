# Tezaver Bulut - Fault Lab Service
"""
Service to manage fault injection profiles and runs.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict
from pathlib import Path

from tezaver.bulut.core.fault_injector import FaultInjector, FaultProfile, FaultTarget
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence

class FaultLabService:
    def __init__(self, persistence: SqlitePersistence, injector: FaultInjector, profiles_dir: str = "data/bulut_rules/fault_profiles"):
        self.db = persistence
        self.injector = injector
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory active state
        self.active_profile_id: Optional[str] = None
        
    def list_profiles(self) -> List[FaultProfile]:
        """List all available fault profiles from disk."""
        profiles = []
        for f in self.profiles_dir.glob("*.json"):
            try:
                with open(f, "r") as fp:
                    data = json.load(fp)
                    profiles.append(FaultProfile.from_dict(data))
            except Exception:
                pass # Skip broken files
        return profiles
        
    def get_profile(self, profile_id: str) -> Optional[FaultProfile]:
        """Get profile by ID."""
        for p in self.list_profiles():
            if p.id == profile_id:
                return p
        return None
        
    def activate_profile(self, profile_id: str) -> bool:
        """Activate a profile for injection."""
        p = self.get_profile(profile_id)
        if not p:
            return False
            
        run_id = str(uuid.uuid4())
        self.active_profile_id = profile_id
        self.injector.load_profile(p, run_id=run_id)
        
        # Persist run start
        self._record_run_start(run_id, profile_id, p.name)
        return True
        
    def deactivate(self):
        """Deactivate injection."""
        if self.injector.active_run_id:
             # Mark as finished? Or user explicitly marks?
             # Let's mark as SUCCESS by default if manual stop.
             self._record_run_end(self.injector.active_run_id, "STOPPED", "Manual deactivation")
             
        self.injector.clear()
        self.active_profile_id = None
        
    def get_active_profile(self) -> Optional[str]:
        return self.active_profile_id

    def get_runs(self, limit: int = 20) -> List[dict]:
        """Get past fault runs."""
        conn = self.db._get_conn()
        conn.row_factory = import_sqlite_row_factory() # Use local import or helper if row_factory not avail on conn
        # Actually persistence methods handle conn.
        # We need a method in persistence or direct query.
        # Let's add method to persistence later or do direct query here (slightly safer to keep db logic in persistence,
        # but for speed and since we have the conn exposed via private method...)
        # Better: Add `get_fault_runs` to persistence?
        # User requirement said "Produce full content". I'll add the method to persistence instead of raw SQL here if possible.
        # But for now, let's just do raw SQL with `row_factory` manually.
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM fault_runs ORDER BY started_ts DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        
        # fetchall returns tuples if no row_factory set on conn creates by `_get_conn`.
        # `_get_conn` does NOT set row_factory in `persistence_sqlite.py`.
        # Usage there sets it locally.
        
        valid_rows = []
        for r in rows:
            # 0:id, 1:prof_id, 2:start, 3:res, 4:note, 5:scen
            valid_rows.append({
                "id": r[0],
                "profile_id": r[1],
                "started_ts": r[2],
                "result": r[3],
                "notes": r[4],
                "scenario_name": r[5]
            })
            
        conn.close()
        return valid_rows

    def _record_run_start(self, run_id: str, profile_id: str, name: str):
        conn = self.db._get_conn()
        cursor = conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT INTO fault_runs (id, profile_id, started_ts, result, notes, scenario_name)
            VALUES (?, ?, ?, 'RUNNING', '', ?)
        """, (run_id, profile_id, now, name))
        conn.commit()
        conn.close()

    def _record_run_end(self, run_id: str, result: str, notes: str):
        conn = self.db._get_conn()
        cursor = conn.cursor()
        cursor.execute("UPDATE fault_runs SET result=?, notes=? WHERE id=?", (result, notes, run_id))
        conn.commit()
        conn.close()

def import_sqlite_row_factory():
    import sqlite3
    return sqlite3.Row
