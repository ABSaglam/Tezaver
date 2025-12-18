# Tezaver Bulut - Constitution Guard
"""
Service to enforce checksum integrity of the Constitution document.
"""

import hashlib
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

class ConstitutionGuard:
    def __init__(self, ctx: Any):
        self._ctx = ctx
        self._cache_ttl = 5.0
        self._last_check_ts = 0.0
        self._cached_result: Optional[Dict[str, Any]] = None

    def compute_checksum(self) -> Optional[str]:
        """Compute SHA256 of the constitution file."""
        if not self._ctx.config.constitution_path:
             return None
             
        path = Path(self._ctx.config.constitution_path)
        if not path.exists():
            return None
            
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()

    def get_current(self) -> Dict[str, Any]:
        """Get current constitution status (cached)."""
        now = time.time()
        if self._cached_result and (now - self._last_check_ts < self._cache_ttl):
            return self._cached_result
            
        path = Path(self._ctx.config.constitution_path)
        exists = path.exists()
        chk = self.compute_checksum()
        mtime = path.stat().st_mtime if exists else 0
        
        self._cached_result = {
            "version": self._ctx.config.constitution_version,
            "path": str(path),
            "sha256": chk,
            "sha256_short": chk[:8] if chk else "N/A",
            "exists": exists,
            "mtime_ts": mtime,
            "ts": now
        }
        self._last_check_ts = now
        return self._cached_result

    def check_and_alert(self) -> Dict[str, Any]:
        """
        Check for Doc Drift and alert if detected.
        Stores new hash in config_snapshots table.
        """
        curr = self.get_current()
        if not curr["exists"]:
            return {"drift": True, "reason": "MISSING"}
            
        new_hash = curr["sha256"]
        
        # check persistence
        last_row = self._ctx.persistence.get_latest_config_snapshot(source="CONSTITUTION")
        old_hash = last_row["hash"] if last_row else None
        
        drift = False
        if old_hash and old_hash != new_hash:
            drift = True
            
            # Alert
            msg = f"Constitution Drift! {old_hash[:8]} -> {new_hash[:8]}"
            print(f"[ConstitutionGuard] {msg}")
            
            self._ctx.telemetry.emit("CONSTITUTION_CHECKSUM_CHANGED", {
                "old": old_hash,
                "new": new_hash
            })
            self._ctx.persistence.insert_alert(
                level="WARN",
                code="DOC_DRIFT",
                message=msg,
                details_json=json.dumps({"old": old_hash, "new": new_hash})
            )

        # Record if changed or new
        if drift or not old_hash:
            content = json.dumps({
                "version": curr["version"],
                "path": curr["path"],
                "sha256": curr["sha256"],
                "mtime": curr["mtime_ts"]
            })
            self._ctx.persistence.insert_config_snapshot(
                hash_val=new_hash,
                mode="DOC",
                content_json=content,
                source="CONSTITUTION"
            )
            
        return {
            "drift": drift,
            "old_hash": old_hash,
            "new_hash": new_hash
        }
