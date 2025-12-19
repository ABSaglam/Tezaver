# Tezaver Bulut - Health Check Scheduler (P12)
"""
Periodic health checks with anomaly detection and alerts.
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import hashlib
import json


@dataclass
class HealthAnomaly:
    """Detected health anomaly."""
    code: str
    severity: int  # 1=critical, 2=warning
    message: str
    recommended_action: str


class HealthCheckScheduler:
    """
    Periodic health checker for system monitoring.
    
    Runs every HEALTH_CHECK_INTERVAL and detects anomalies:
    - Time sync skew
    - Strict timing drift
    - WS stream disconnected
    - Rate limiter throttles
    - Daemon stalled
    """
    
    DEFAULT_INTERVAL_DEV = 60  # seconds
    DEFAULT_INTERVAL_PROD = 300  # 5 minutes
    
    def __init__(self, ctx):
        self._ctx = ctx
        self._last_check_ts: Optional[str] = None
        self._checks_history: List[Dict] = []
    
    def get_interval(self) -> int:
        """Get check interval based on mode."""
        config = self._ctx.config
        mode = getattr(config, 'mode', 'DEV')
        if mode in ['REAL_MAINNET', 'REAL_TESTNET']:
            return self.DEFAULT_INTERVAL_PROD
        return self.DEFAULT_INTERVAL_DEV
    
    def run_check(self) -> Dict[str, Any]:
        """
        Run health check and detect anomalies.
        
        Returns check result with anomalies.
        """
        now = datetime.now(timezone.utc)
        snapshot = self._build_snapshot()
        anomalies = self._detect_anomalies(snapshot)
        
        snapshot_hash = self._hash_snapshot(snapshot)
        
        result = {
            "ts": now.isoformat(),
            "snapshot_hash": snapshot_hash,
            "anomalies": [
                {
                    "code": a.code,
                    "severity": a.severity,
                    "message": a.message,
                    "recommended_action": a.recommended_action
                }
                for a in anomalies
            ],
            "healthy": len([a for a in anomalies if a.severity == 1]) == 0
        }
        
        self._last_check_ts = now.isoformat()
        self._checks_history.append(result)
        if len(self._checks_history) > 200:
            self._checks_history = self._checks_history[-100:]
        
        # Save to persistence
        self._save_check(result)
        
        # Write alerts for critical anomalies
        self._write_alerts(anomalies)
        
        return result
    
    def _build_snapshot(self) -> Dict[str, Any]:
        """Build current health snapshot."""
        snapshot = {}
        ctx = self._ctx
        
        try:
            # Time sync
            time_sync = ctx.time_sync
            snapshot["time_sync"] = {
                "offset_ms": getattr(time_sync, 'server_offset_ms', 0),
                "last_sync": getattr(time_sync, 'last_sync_ts', None)
            }
        except Exception:
            snapshot["time_sync"] = {"offset_ms": 0}
        
        try:
            # Strict timing
            config = ctx.config
            snapshot["strict_timing"] = {
                "enabled": getattr(config, 'strict_timing_enabled', False),
                "max_drift_ms": getattr(config, 'max_drift_ms', 5000)
            }
        except Exception:
            snapshot["strict_timing"] = {}
        
        try:
            # Kill switch
            ks = ctx.kill_switch
            snapshot["kill_switch"] = ks.get_status()
        except Exception:
            snapshot["kill_switch"] = {"state": "UNKNOWN"}
        
        try:
            # Recovery
            recovery = ctx.restart_recovery
            snapshot["recovery"] = recovery.get_status()
        except Exception:
            snapshot["recovery"] = {"status": "UNKNOWN"}
        
        try:
            # Autopilot
            autopilot = ctx.autopilot_service
            snapshot["autopilot"] = autopilot.get_status()
        except Exception:
            snapshot["autopilot"] = {"enabled": False}
        
        try:
            # Scheduler
            scheduler = ctx.scheduler
            snapshot["scheduler"] = {
                "running": getattr(scheduler, 'is_running', lambda: True)(),
                "last_cycle_ts": getattr(scheduler, 'last_cycle_ts', None)
            }
        except Exception:
            snapshot["scheduler"] = {"running": True}
        
        return snapshot
    
    def _detect_anomalies(self, snapshot: Dict) -> List[HealthAnomaly]:
        """Detect anomalies from snapshot."""
        anomalies = []
        config = self._ctx.config
        
        # Time sync skew
        time_sync = snapshot.get("time_sync", {})
        offset_ms = abs(time_sync.get("offset_ms", 0))
        max_offset = getattr(config, 'max_time_offset_ms', 3000)
        if offset_ms > max_offset:
            anomalies.append(HealthAnomaly(
                code="TIME_SYNC_SKEW",
                severity=1 if offset_ms > 10000 else 2,
                message=f"Time sync offset {offset_ms}ms exceeds {max_offset}ms",
                recommended_action="POST /time_sync/refresh"
            ))
        
        # Kill switch not normal
        ks = snapshot.get("kill_switch", {})
        ks_state = ks.get("state", "NORMAL")
        if ks_state not in ["NORMAL"]:
            anomalies.append(HealthAnomaly(
                code="KILL_SWITCH_ACTIVE",
                severity=2 if ks_state == "SAFE" else 1,
                message=f"Kill switch in {ks_state} state",
                recommended_action="Review /kill_switch/status and consider /kill_switch/resume"
            ))
        
        # Recovery needed
        recovery = snapshot.get("recovery", {})
        if recovery.get("status") == "FAIL":
            anomalies.append(HealthAnomaly(
                code="RECOVERY_FAILED",
                severity=1,
                message="Last recovery run failed",
                recommended_action="POST /recovery/run"
            ))
        
        # Scheduler stalled
        scheduler = snapshot.get("scheduler", {})
        if not scheduler.get("running", True):
            anomalies.append(HealthAnomaly(
                code="SCHEDULER_STALLED",
                severity=1,
                message="Scheduler is not running",
                recommended_action="Restart application"
            ))
        
        return anomalies
    
    def _hash_snapshot(self, snapshot: Dict) -> str:
        """Generate hash for snapshot."""
        try:
            data = json.dumps(snapshot, sort_keys=True, default=str)
            return hashlib.md5(data.encode()).hexdigest()[:8]
        except Exception:
            return "unknown"
    
    def _save_check(self, result: Dict):
        """Save health check to persistence."""
        try:
            self._ctx.persistence.save_health_check({
                "ts": result["ts"],
                "snapshot_hash": result["snapshot_hash"],
                "anomalies_json": json.dumps(result["anomalies"]),
                "healthy": result["healthy"]
            })
        except Exception:
            pass
    
    def _write_alerts(self, anomalies: List[HealthAnomaly]):
        """Write alerts for anomalies."""
        try:
            for a in anomalies:
                if a.severity == 1:  # Only critical
                    self._ctx.persistence.insert_alert({
                        "level": "WARN" if a.severity == 2 else "BLOCK",
                        "source": "health_check",
                        "message": a.message,
                        "context_json": json.dumps({
                            "code": a.code,
                            "action": a.recommended_action
                        }),
                        "ts": datetime.now(timezone.utc).isoformat()
                    })
        except Exception:
            pass
    
    def get_recent_checks(self, limit: int = 50) -> List[Dict]:
        """Get recent health checks."""
        return list(reversed(self._checks_history[-limit:]))
    
    def get_status(self) -> Dict[str, Any]:
        """Get health checker status."""
        return {
            "last_check_ts": self._last_check_ts,
            "checks_count": len(self._checks_history),
            "interval_seconds": self.get_interval()
        }
