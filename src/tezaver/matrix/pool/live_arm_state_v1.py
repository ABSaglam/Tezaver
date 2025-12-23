"""
Live Arm State V1
=================

Writer for LIVE arm state reports.
"""
import hashlib
from typing import Dict, Any, Optional, List
from tezaver.matrix.pool.pool_models_v1 import LiveArmStateReportV1
from tezaver.matrix.pool.pool_reports_v1 import resolve_reports_dir, write_report_json, now_iso

def generate_arm_id(run_id: str, bundle_id: Optional[str]) -> str:
    """Generate deterministic arm ID."""
    raw = f"{run_id}|{bundle_id or 'NONE'}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]

def write_live_arm_state_report(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    arm_state: Dict[str, Any]
) -> str:
    """
    Write LIVE arm state report.
    
    Args:
        stage: Run stage (should be "live")
        run_id: Run ID
        trace_ctx: {"engine_version":..., "data_fingerprint":..., "config_signature":...}
        arm_state: {
            "arm_id": optional,
            "armed": bool,
            "arm_reason": str,
            "bundle_id": optional,
            "symbol": optional,
            "timeframe": optional,
            "qc_score": optional,
            "tier": optional,
            "notes": list
        }
        
    Returns:
        Path to written report
    """
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    reports_dir = resolve_reports_dir(stage, run_id)
    
    arm_id = arm_state.get("arm_id") or generate_arm_id(run_id, arm_state.get("bundle_id"))
    
    report = LiveArmStateReportV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        arm_id=arm_id,
        armed=arm_state.get("armed", False),
        arm_reason=arm_state.get("arm_reason", "DISARMED"),
        bundle_id=arm_state.get("bundle_id"),
        symbol=arm_state.get("symbol"),
        timeframe=arm_state.get("timeframe"),
        qc_score=arm_state.get("qc_score"),
        tier=arm_state.get("tier"),
        notes=arm_state.get("notes", [])
    )
    
    path = reports_dir / "live_arm_state_report_v1.json"
    write_report_json(path, report.to_dict())
    
    return str(path)
