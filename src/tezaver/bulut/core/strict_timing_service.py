# Tezaver Bulut - Strict Timing Service
"""
Service to enforce Strictly-Once Cycle Execution and Drift Guard.
"""
from datetime import datetime, timezone
from typing import Dict, Any

from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.core.config import BulutConfig

class StrictTimingService:
    def __init__(self, persistence: SqlitePersistence, config: BulutConfig, telemetry):
        self.db = persistence
        self.config = config
        self.telemetry = telemetry

    def on_cycle_attempt(self, bar_close_ts: datetime, now_ts: datetime) -> Dict[str, Any]:
        """
        Check if we should run a cycle for this bar close timestamp.
        Returns:
            {
                "status": "ALLOW" | "BLOCK",
                "reason": "OK" | "DEDUPED" | "DRIFT_TOO_HIGH",
                "drift_ms": int,
                "metadata": dict
            }
        """
        if not self.config.strict_timing_enabled:
            return {"status": "ALLOW", "reason": "DISABLED", "drift_ms": 0}

        # 1. Dedupe Check
        bar_ts_iso = bar_close_ts.isoformat()
        existing = self.db.check_dedupe_run(bar_ts_iso)
        
        if existing:
            # Already ran!
            self.telemetry.emit("STRICT_TIMING_DEDUPED", {
                "bar_close_ts": bar_ts_iso,
                "prev_run_ts": existing["run_ts"],
                "last_cycle_id": existing["last_cycle_id"]
            })
            return {
                "status": "BLOCK",
                "reason": "DEDUPED",
                "drift_ms": 0,
                "metadata": existing
            }

        # 2. Drift Check
        # Convert to ms
        close_ms = bar_close_ts.timestamp() * 1000
        now_ms = now_ts.timestamp() * 1000
        drift_ms = int(now_ms - close_ms)
        
        meta = {
            "drift_ms": drift_ms,
            "threshold": self.config.max_drift_ms
        }

        if drift_ms > self.config.max_drift_ms:
            # Alert
            self.telemetry.emit("STRICT_TIMING_DRIFT_ALERT", meta)
            # In MAINNET, we might want to BLOCK if drift is massive to avoid trading on stale data.
            # But the user spec said "BLOCK/ALERT".
            # "Threshold aşılırsa ALERT + ops banner." -> Doesn't explicitly say BLOCK.
            # But in "Proof Tests" section: "MAINNET mode policy: drift -> BLOCK (safer)"
            # Let's verify config mode.
            if self.config.mode == "MAINNET" or self.config.mode == "REAL":
                 return {
                     "status": "BLOCK", 
                     "reason": "DRIFT_VIOLATION", 
                     "drift_ms": drift_ms,
                     "metadata": meta
                 }
            else:
                # Just alert in testnet/dev
                pass

        return {
            "status": "ALLOW",
            "reason": "OK",
            "drift_ms": drift_ms,
            "metadata": meta
        }

    def record_success(self, bar_close_ts: datetime, cycle_id: int):
        """Mark cycle as successfully run."""
        if not self.config.strict_timing_enabled:
            return
            
        now = datetime.now(timezone.utc)
        self.db.register_dedupe_run(
            bar_close_ts.isoformat(),
            cycle_id,
            now.isoformat(),
            int(now.timestamp() * 1000)
        )
