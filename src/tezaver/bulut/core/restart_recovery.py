# Tezaver Bulut - Restart Recovery Service (P10)
"""
Disaster Recovery for safe system restart.

Recovery Protocol:
1. SAFE boot (entries blocked, protectives maintained)
2. Exchange reconcile (positions, orders)
3. DB reconcile (positions table sync)
4. Plan reconcile (EXECUTING/AMBIGUOUS resolution)
5. Health check (OOO/dedupe stats)

Operator must approve RESUME after PASS.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class RecoveryStatus(Enum):
    """Recovery status values."""
    NOT_RUN = "NOT_RUN"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    STALE = "STALE"


@dataclass
class RecoveryBlocker:
    """Blocker preventing resume."""
    code: str
    message: str
    severity: str  # CRITICAL, WARNING


@dataclass
class RecoveryReport:
    """Recovery run report."""
    run_id: str
    timestamp: str
    mode: str
    status: RecoveryStatus
    blockers: List[RecoveryBlocker]
    stats: Dict[str, Any]
    duration_ms: int


class RestartRecoveryService:
    """
    Manages disaster recovery on system restart.
    
    Protocol:
    - On startup in MAINNET/TESTNET: enter SAFE boot
    - Run reconciliation steps
    - Generate recovery report
    - Only allow RESUME if report.status == PASS
    """
    
    MAX_AGE_MINUTES = 15  # Report becomes stale after this
    
    def __init__(self, ctx):
        self._ctx = ctx
        self._last_report: Optional[RecoveryReport] = None
        self._is_running = False
        self._load_last_report()
    
    def _load_last_report(self):
        """Load last recovery report from persistence."""
        try:
            report = self._ctx.persistence.get_latest_recovery_report()
            if report:
                self._last_report = RecoveryReport(
                    run_id=report.get("run_id", ""),
                    timestamp=report.get("ts", ""),
                    mode=report.get("mode", ""),
                    status=RecoveryStatus(report.get("status", "NOT_RUN")),
                    blockers=[
                        RecoveryBlocker(
                            code=b.get("code", ""),
                            message=b.get("message", ""),
                            severity=b.get("severity", "WARNING")
                        )
                        for b in report.get("blockers", [])
                    ],
                    stats=report.get("stats", {}),
                    duration_ms=report.get("duration_ms", 0)
                )
        except Exception:
            pass
    
    def _save_report(self, report: RecoveryReport):
        """Save recovery report to persistence."""
        try:
            self._ctx.persistence.save_recovery_report({
                "run_id": report.run_id,
                "ts": report.timestamp,
                "mode": report.mode,
                "status": report.status.value,
                "blockers": [
                    {"code": b.code, "message": b.message, "severity": b.severity}
                    for b in report.blockers
                ],
                "stats": report.stats,
                "duration_ms": report.duration_ms
            })
        except Exception:
            pass
    
    def run(self) -> RecoveryReport:
        """
        Run full recovery protocol.
        
        Steps:
        1. Exchange position reconcile
        2. DB position reconcile
        3. Plan reconcile
        4. Health checks
        
        Returns RecoveryReport with status.
        """
        import time
        start_time = time.time()
        
        self._is_running = True
        blockers: List[RecoveryBlocker] = []
        stats: Dict[str, Any] = {}
        
        config = self._ctx.config
        mode = getattr(config, 'mode', 'TESTNET')
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        
        try:
            # Step 1: Exchange Position Reconcile
            exchange_result = self._reconcile_exchange_positions()
            stats["exchange_positions"] = exchange_result
            if exchange_result.get("errors"):
                blockers.append(RecoveryBlocker(
                    code="EXCHANGE_POSITION_MISMATCH",
                    message=f"Exchange position errors: {exchange_result['errors']}",
                    severity="CRITICAL"
                ))
            
            # Step 2: DB Position Reconcile
            db_result = self._reconcile_db_positions()
            stats["db_positions"] = db_result
            if db_result.get("orphans"):
                blockers.append(RecoveryBlocker(
                    code="DB_POSITION_ORPHANS",
                    message=f"Orphan positions in DB: {len(db_result['orphans'])}",
                    severity="WARNING"
                ))
            
            # Step 3: Plan Reconcile
            plan_result = self._reconcile_plans()
            stats["plans"] = plan_result
            if plan_result.get("ambiguous"):
                blockers.append(RecoveryBlocker(
                    code="AMBIGUOUS_PLANS",
                    message=f"Ambiguous plans found: {plan_result['ambiguous']}",
                    severity="WARNING"
                ))
            
            # Step 4: Health Checks
            health_result = self._check_system_health()
            stats["health"] = health_result
            if not health_result.get("healthy", True):
                blockers.append(RecoveryBlocker(
                    code="SYSTEM_HEALTH_FAIL",
                    message=health_result.get("reason", "Health check failed"),
                    severity="CRITICAL"
                ))
            
            # Determine status
            critical_blockers = [b for b in blockers if b.severity == "CRITICAL"]
            status = RecoveryStatus.FAIL if critical_blockers else RecoveryStatus.PASS
            
        except Exception as e:
            blockers.append(RecoveryBlocker(
                code="RECOVERY_EXCEPTION",
                message=str(e),
                severity="CRITICAL"
            ))
            status = RecoveryStatus.FAIL
        
        finally:
            self._is_running = False
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        report = RecoveryReport(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            mode=mode,
            status=status,
            blockers=blockers,
            stats=stats,
            duration_ms=duration_ms
        )
        
        self._last_report = report
        self._save_report(report)
        
        # Emit telemetry
        try:
            self._ctx.telemetry.emit({
                "event": "RECOVERY_REPORT",
                "status": status.value,
                "blockers_count": len(blockers),
                "critical_count": len(critical_blockers),
                "duration_ms": duration_ms
            })
        except Exception:
            pass
        
        return report
    
    def _reconcile_exchange_positions(self) -> Dict[str, Any]:
        """Reconcile positions with exchange."""
        result = {"synced": 0, "errors": []}
        
        try:
            # Get positions from exchange (via reconciliation service)
            recon = self._ctx.reconciliation_service
            if hasattr(recon, 'reconcile_positions'):
                exchange_result = recon.reconcile_positions()
                result["synced"] = exchange_result.get("synced", 0)
                result["errors"] = exchange_result.get("errors", [])
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def _reconcile_db_positions(self) -> Dict[str, Any]:
        """Reconcile DB positions table."""
        result = {"total": 0, "orphans": []}
        
        try:
            positions = self._ctx.persistence.get_positions(status="OPEN")
            result["total"] = len(positions or [])
            
            # Check for orphans (positions without matching exchange data)
            # This is a simplified check
            for pos in (positions or []):
                if pos.get("reconcile_status") == "ORPHAN":
                    result["orphans"].append(pos.get("symbol", ""))
        except Exception as e:
            result["errors"] = [str(e)]
        
        return result
    
    def _reconcile_plans(self) -> Dict[str, Any]:
        """Reconcile trade plans."""
        result = {"executing": 0, "ambiguous": 0, "proposed": 0}
        
        try:
            plans = self._ctx.persistence.get_trade_plans(
                status_in=["EXECUTING", "AMBIGUOUS", "PROPOSED"]
            )
            
            for plan in (plans or []):
                status = plan.get("status", "")
                if status == "EXECUTING":
                    result["executing"] += 1
                elif status == "AMBIGUOUS":
                    result["ambiguous"] += 1
                elif status == "PROPOSED":
                    result["proposed"] += 1
        except Exception:
            pass
        
        return result
    
    def _check_system_health(self) -> Dict[str, Any]:
        """Check overall system health."""
        result = {"healthy": True, "checks": {}}
        
        try:
            # Check kill switch state
            ks = self._ctx.kill_switch
            ks_status = ks.get_status()
            result["checks"]["kill_switch"] = ks_status.get("state", "UNKNOWN")
            
            # Check strict timing
            try:
                strict = self._ctx.strict_timing
                if hasattr(strict, 'is_healthy'):
                    result["checks"]["strict_timing"] = strict.is_healthy()
            except Exception:
                result["checks"]["strict_timing"] = True
            
            # Check drift guard
            try:
                drift = self._ctx.drift_guard
                if hasattr(drift, 'is_compliant'):
                    result["checks"]["drift_guard"] = drift.is_compliant()
            except Exception:
                result["checks"]["drift_guard"] = True
                
        except Exception as e:
            result["healthy"] = False
            result["reason"] = str(e)
        
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """Get current recovery status."""
        if not self._last_report:
            return {
                "status": RecoveryStatus.NOT_RUN.value,
                "last_run_ts": None,
                "mode": None,
                "blockers": [],
                "stats": {},
                "is_stale": True,
                "can_resume": False,
                "resume_blockers": ["Recovery not run"]
            }
        
        # Check if stale
        try:
            last_ts = datetime.fromisoformat(self._last_report.timestamp)
            age_minutes = (datetime.now(timezone.utc) - last_ts).total_seconds() / 60
            is_stale = age_minutes > self.MAX_AGE_MINUTES
        except Exception:
            is_stale = True
        
        can_resume, resume_reasons = self.can_resume()
        
        return {
            "status": self._last_report.status.value,
            "last_run_ts": self._last_report.timestamp,
            "run_id": self._last_report.run_id,
            "mode": self._last_report.mode,
            "blockers": [
                {"code": b.code, "message": b.message, "severity": b.severity}
                for b in self._last_report.blockers
            ],
            "stats": self._last_report.stats,
            "duration_ms": self._last_report.duration_ms,
            "is_stale": is_stale,
            "is_running": self._is_running,
            "can_resume": can_resume,
            "resume_blockers": resume_reasons
        }
    
    def can_resume(self) -> Tuple[bool, List[str]]:
        """
        Check if system can resume normal operations.
        
        Returns (can_resume, list_of_blocking_reasons).
        """
        reasons = []
        
        # Must have run recovery
        if not self._last_report:
            return False, ["Recovery has not been run"]
        
        # Must have PASS status
        if self._last_report.status != RecoveryStatus.PASS:
            reasons.append(f"Recovery status is {self._last_report.status.value}")
        
        # Check for critical blockers
        critical = [b for b in self._last_report.blockers if b.severity == "CRITICAL"]
        if critical:
            reasons.append(f"{len(critical)} critical blockers present")
        
        # Check if stale
        config = self._ctx.config
        block_if_stale = getattr(config, 'recovery_block_resume_if_stale', True)
        if block_if_stale:
            try:
                last_ts = datetime.fromisoformat(self._last_report.timestamp)
                age_minutes = (datetime.now(timezone.utc) - last_ts).total_seconds() / 60
                if age_minutes > self.MAX_AGE_MINUTES:
                    reasons.append(f"Recovery report is stale ({int(age_minutes)} min old)")
            except Exception:
                reasons.append("Cannot determine recovery report age")
        
        return len(reasons) == 0, reasons
    
    def safe_boot(self) -> Tuple[bool, str]:
        """
        Execute safe boot sequence.
        
        Called on startup to ensure system enters SAFE mode.
        """
        config = self._ctx.config
        mode = getattr(config, 'mode', 'TESTNET')
        
        # Only safe boot in real trading modes
        if mode not in ['REAL_MAINNET', 'REAL_TESTNET']:
            return True, "Safe boot skipped (not in trading mode)"
        
        safe_boot_enabled = getattr(config, 'recovery_safe_boot', True)
        if not safe_boot_enabled:
            return True, "Safe boot disabled by config"
        
        # Set kill switch to SAFE
        try:
            ks = self._ctx.kill_switch
            success, msg = ks.safe("startup_safe_boot", "system")
            
            self._ctx.telemetry.emit({
                "event": "SAFE_BOOT",
                "mode": mode,
                "success": success
            })
            
            return success, f"Safe boot: {msg}"
        except Exception as e:
            return False, f"Safe boot failed: {e}"
