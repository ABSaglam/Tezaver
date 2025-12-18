# Tezaver Bulut - Migration Runner
"""
Service to discover and apply DB migrations.
"""

import importlib
import pkgutil
import sqlite3
from typing import List, Dict, Any
from pathlib import Path
from tezaver.bulut import migrations

class MigrationRunner:
    def __init__(self, persistence):
        self._persistence = persistence
        
    def _discover_migrations(self) -> List[Any]:
        """Dynamically discover migration modules in order."""
        package = migrations
        modules = []
        path = Path(package.__file__).parent
        
        for _, name, _ in pkgutil.iter_modules([str(path)]):
            mod = importlib.import_module(f"tezaver.bulut.migrations.{name}")
            if hasattr(mod, "version") and hasattr(mod, "apply"):
                modules.append(mod)
        
        # Sort by version
        modules.sort(key=lambda m: m.version)
        return modules

    def run_pending(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run pending migrations.
        dry_run: If True, returns planned SQL without executing.
        """
        current_ver = self._persistence.get_schema_version()
        all_migrations = self._discover_migrations()
        pending = [m for m in all_migrations if m.version > current_ver]
        
        report = {
            "current_version": current_ver,
            "target_version": all_migrations[-1].version if all_migrations else 0,
            "pending_count": len(pending),
            "executed": [],
            "dry_run": dry_run
        }
        
        if not pending:
            return report
            
        if dry_run:
            plan = []
            for m in pending:
                desc = getattr(m, "description", "")
                sql_list = m.dry_run() if hasattr(m, "dry_run") else ["(No dry_run source)"]
                plan.append({
                    "version": m.version,
                    "description": desc,
                    "sql": sql_list
                })
            report["plan"] = plan
            return report
            
        # Apply Logic
        conn = self._persistence._get_conn() # Access raw conn for transaction
        cursor = conn.cursor()
        
        try:
            for m in pending:
                print(f"[Migration] Applying v{m.version}: {getattr(m, 'description', '')}")
                m.apply(cursor)
                # Update schema version atomically with the migration steps
                # Wait, we usually update meta at end of batch or end of each?
                # Safer: End of EACH. If script fails, previous ones committed?
                # SQLite commits on conn.commit().
                # We should commit after EACH migration to be safe (checkpoint).
                # But if middle fails, we resume from there.
                
                cursor.execute("""
                    INSERT INTO schema_meta (key, value) VALUES ('schema_version', ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value
                """, (str(m.version),))
                
                conn.commit()
                report["executed"].append(m.version)
                report["current_version"] = m.version
                
        except Exception as e:
            conn.rollback() # Rollback current failing migration
            print(f"[Migration] FAILED at v{m.version if 'm' in locals() else '?'}: {e}")
            raise e
        finally:
            conn.close()
            
        return report
