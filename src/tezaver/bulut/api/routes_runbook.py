# Tezaver Bulut - Runbook Snapshot API (P11)
"""
REST endpoint for Operator Runbook snapshot.
Returns all status data in a single payload for fast UI rendering.
"""
from fastapi import APIRouter, Request
from typing import Dict, Any


router = APIRouter(prefix="/runbook", tags=["runbook"])


def get_ctx(request: Request):
    """Get context from app state."""
    return request.app.state.context


@router.get("/snapshot")
async def get_runbook_snapshot(request: Request) -> Dict[str, Any]:
    """
    Get complete runbook snapshot for operator UI.
    
    Returns all status data in a single request:
    - Mode/security
    - Guards (constitution, drift)
    - Timing (strict, sync, exchangeinfo)
    - Checklist/proof
    - Pilot/expansion
    - Autopilot
    - Allocation
    - Exit intel
    - Kill switch
    - Recovery
    - Forensics
    - Test reports
    """
    ctx = get_ctx(request)
    snapshot = {}
    
    try:
        config = ctx.config
        state = ctx.state
        
        # 1. Mode + Security
        snapshot["mode"] = {
            "current": getattr(config, 'mode', 'UNKNOWN'),
            "ops_auth_enabled": getattr(config, 'ops_auth_enabled', False),
            "allowed_hosts": getattr(config, 'allowed_hosts', []),
            "is_mainnet": getattr(config, 'mode', '') == 'REAL_MAINNET'
        }
        
        # 2. Constitution + Drift Guard
        try:
            constitution = ctx.constitution_guard
            snapshot["constitution"] = {
                "enabled": getattr(constitution, 'enabled', False),
                "locked": getattr(constitution, 'is_locked', lambda: False)(),
                "reason": getattr(constitution, 'lock_reason', None)
            }
        except Exception:
            snapshot["constitution"] = {"enabled": False, "locked": False}
        
        try:
            drift = ctx.drift_guard
            snapshot["drift_guard"] = {
                "enabled": getattr(drift, 'enabled', False),
                "compliant": getattr(drift, 'is_compliant', lambda: True)(),
                "hash": getattr(drift, 'current_hash', None)
            }
        except Exception:
            snapshot["drift_guard"] = {"enabled": False, "compliant": True}
        
        # 3. Strict Timing + Time Sync
        try:
            snapshot["strict_timing"] = {
                "enabled": getattr(config, 'strict_timing_enabled', False),
                "max_drift_ms": getattr(config, 'max_drift_ms', 5000)
            }
        except Exception:
            snapshot["strict_timing"] = {"enabled": False}
        
        try:
            time_sync = ctx.time_sync
            snapshot["time_sync"] = {
                "last_sync_ts": getattr(time_sync, 'last_sync_ts', None),
                "offset_ms": getattr(time_sync, 'server_offset_ms', 0)
            }
        except Exception:
            snapshot["time_sync"] = {"last_sync_ts": None}
        
        try:
            exchangeinfo = ctx.exchangeinfo_cache
            snapshot["exchangeinfo"] = {
                "symbols_count": getattr(exchangeinfo, 'symbols_count', lambda: 0)(),
                "last_refresh": getattr(exchangeinfo, 'last_refresh_ts', None)
            }
        except Exception:
            snapshot["exchangeinfo"] = {"symbols_count": 0}
        
        # 4. Launch Checklist + Proof Ladder
        try:
            checklist = ctx.launch_checklist
            snapshot["launch_checklist"] = {
                "passed": getattr(checklist, 'is_passed', lambda: False)(),
                "items_passed": getattr(checklist, 'passed_count', lambda: 0)(),
                "items_total": getattr(checklist, 'total_count', lambda: 0)()
            }
        except Exception:
            snapshot["launch_checklist"] = {"passed": False}
        
        try:
            proof = ctx.proof_ladder
            snapshot["proof_ladder"] = {
                "current_step": getattr(proof, 'current_step', 0),
                "total_steps": getattr(proof, 'total_steps', 5),
                "last_eval": getattr(proof, 'last_evaluation_ts', None)
            }
        except Exception:
            snapshot["proof_ladder"] = {"current_step": 0, "total_steps": 5}
        
        # 5. Pilot Meter + Expansion
        try:
            pilot = ctx.pilot_meter
            snapshot["pilot_meter"] = pilot.get_status()
        except Exception:
            snapshot["pilot_meter"] = {"committed_usdt": 0, "limit_usdt": 50}
        
        try:
            expansion = ctx.expansion_policy
            snapshot["expansion"] = expansion.get_status()
        except Exception:
            snapshot["expansion"] = {"current_tier": 0, "tier_limit": 50}
        
        # 6. Autopilot
        try:
            autopilot = ctx.autopilot_service
            snapshot["autopilot"] = autopilot.get_status()
        except Exception:
            snapshot["autopilot"] = {"enabled": False}
        
        # 7. Allocation
        try:
            allocation = ctx.allocation_engine
            snapshot["allocation"] = allocation.get_status()
        except Exception:
            snapshot["allocation"] = {"total_used_usdt": 0}
        
        # 8. Exit Intel
        try:
            exit_intel = ctx.exit_intel_engine
            snapshot["exit_intel"] = exit_intel.get_status()
        except Exception:
            snapshot["exit_intel"] = {"profiles_loaded": 0}
        
        # 9. Kill Switch
        try:
            kill_switch = ctx.kill_switch
            snapshot["kill_switch"] = kill_switch.get_status()
        except Exception:
            snapshot["kill_switch"] = {"state": "NORMAL"}
        
        # 10. Recovery
        try:
            recovery = ctx.restart_recovery
            snapshot["recovery"] = recovery.get_status()
        except Exception:
            snapshot["recovery"] = {"status": "NOT_RUN", "can_resume": False}
        
        # 11. Forensics (cycles + incidents)
        try:
            cycles = ctx.persistence.get_recent_cycles(limit=5)
            snapshot["forensics"] = {
                "recent_cycles": len(cycles or []),
                "last_cycle_ts": cycles[0].get("ts") if cycles else None
            }
        except Exception:
            snapshot["forensics"] = {"recent_cycles": 0}
        
        # 12. Test Reports
        try:
            import os
            report_path = "data/bulut_ops/test_reports/latest.xml"
            snapshot["test_reports"] = {
                "exists": os.path.exists(report_path),
                "path": report_path,
                "mtime": os.path.getmtime(report_path) if os.path.exists(report_path) else None
            }
        except Exception:
            snapshot["test_reports"] = {"exists": False}
        
        snapshot["ok"] = True
        
    except Exception as e:
        snapshot["ok"] = False
        snapshot["error"] = str(e)
    
    return snapshot
