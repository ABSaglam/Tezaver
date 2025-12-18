# Tezaver Bulut - Config Snapshot
"""
Service for calculating redacted configuration snapshots and hashes.
"""

import json
import hashlib
from typing import Any, Dict
from dataclasses import asdict

from tezaver.bulut.core.config import BulutConfig

class ConfigSnapshotService:
    def __init__(self):
        pass

    def snapshot_config(self, ctx: Any) -> Dict[str, Any]:
        """
        Create a redacted snapshot of the current configuration.
        """
        cfg = ctx.config
        # Convert dataclass to dict
        if isinstance(cfg, BulutConfig):
            data = asdict(cfg)
        else:
            data = dict(cfg) # Fallback if mock/dict
            
        return self._redact(data)

    def hash_config(self, snapshot: Dict[str, Any]) -> str:
        """
        Calculate canonical hash of the snapshot.
        """
        # Sort keys for determinism
        s = json.dumps(snapshot, sort_keys=True)
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def _redact(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact sensitive keys containing KEY, SECRET, TOKEN.
        """
        redacted = {}
        for k, v in data.items():
            k_upper = k.upper()
            if "KEY" in k_upper or "SECRET" in k_upper or "TOKEN" in k_upper:
                # Keep if it is "listen_key" (dynamic, maybe keep?)
                # Prompt says: "keys içinde 'KEY', 'SECRET', 'TOKEN' geçenler => '***REDACTED***'"
                # "listen_key" contains KEY. But it's transient.
                # "api_key" contains KEY.
                # Let's follow rule strictly.
                redacted[k] = "***REDACTED***"
            else:
                redacted[k] = v
        
        # Sort keys in result for cleanliness (though hash helper sorts too)
        return dict(sorted(redacted.items()))
