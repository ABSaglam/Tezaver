# Tezaver Bulut - Drift Guard
"""
Service to detect configuration drift by comparing current snapshot with persistence.
"""

import json
from typing import Any, Dict, Optional

class DriftGuard:
    def __init__(self, ctx: Any):
        self._ctx = ctx
        # Dependencies from ctx lazy or passed in init?
        # The service needs config_snapshot service and persistence.
        # We'll access them via ctx.

    def check_and_record(self, source: str = "MANUAL") -> Dict[str, Any]:
        """
        Check for drift and record the current snapshot.
        Returns: {
            "old_hash": str|None,
            "new_hash": str,
            "drift": bool,
            "source": str
        }
        """
        # 1. Take Snapshot
        snapshot = self._ctx.config_snapshot.snapshot_config(self._ctx)
        new_hash = self._ctx.config_snapshot.hash_config(snapshot)
        content_json = json.dumps(snapshot, sort_keys=True)
        mode = self._ctx.config.mode

        # 2. Get Last from DB
        last_row = self._ctx.persistence.get_latest_config_snapshot()
        old_hash = last_row["hash"] if last_row else None
        
        drift = False
        
        if old_hash and old_hash != new_hash:
            drift = True
            print(f"[DriftGuard] CONFIG DRIFT DETECTED! Old: {old_hash[:8]} -> New: {new_hash[:8]}")
            
            self._ctx.telemetry.emit("CONFIG_DRIFT_DETECTED", {
                "old_hash": old_hash,
                "new_hash": new_hash,
                "mode": mode,
                "source": source
            })
            
            # Alert
            # Use persistence to insert alert directly or via some alert manager
            self._ctx.persistence.insert_alert(
                level="WARN",
                code="CONFIG_DRIFT",
                message=f"Configuration drift detected ({source})",
                details={"old": old_hash, "new": new_hash}
            )

        # 3. Record (Always record to establish new baseline? Or only if changed?)
        # Prompt: "insert_config_snapshot(...)". 
        # If we record every time, we fill DB. 
        # But if we don't record, we drift forever against "ancient" config.
        # "Startup’ta: drift_guard.check_and_record" -> Implies verifying start state.
        # If I change config intentionally (restart), I want that to be the new baseline.
        # So yes, we accept the new config as current.
        # Drift checks change *since last run/save*.
        
        if not old_hash or drift or source == "MANUAL":
            self._ctx.persistence.insert_config_snapshot(
                hash_val=new_hash,
                mode=mode,
                content_json=content_json,
                source=source
            )
            self._ctx.telemetry.emit("CONFIG_SNAPSHOT_SAVED", {
                "hash": new_hash,
                "mode": mode,
                "source": source
            })

        return {
            "old_hash": old_hash,
            "new_hash": new_hash,
            "drift": drift,
            "source": source
        }
