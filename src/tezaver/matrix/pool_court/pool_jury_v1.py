"""
Pool Jury V1
============

Builds scorecard from pool evidence artifacts.
"""
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

from tezaver.matrix.pool_court.pool_court_models_v1 import PoolJuryScorecardV1

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _read_json_safe(path: Path) -> Dict[str, Any]:
    """Read JSON file safely, return empty dict if missing/invalid."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

def build_pool_scorecard(
    reports_dir: Path,
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str]
) -> PoolJuryScorecardV1:
    """
    Build pool scorecard by reading all evidence artifacts.
    
    Args:
        reports_dir: Path to run's reports directory
        stage: Run stage
        run_id: Run ID
        trace_ctx: {"engine_version":..., "data_fingerprint":..., "config_signature":...}
        
    Returns:
        PoolJuryScorecardV1
    """
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    
    key_notes: List[str] = []
    evidence_ok = True
    
    # 1. Pool Mode
    pool_mode = _read_json_safe(reports_dir / "pool_mode_v1.json")
    if not pool_mode.get("pool_enabled"):
        evidence_ok = False
        key_notes.append("MISSING_OR_DISABLED:pool_mode")
    
    # 2. Universe
    universe = _read_json_safe(reports_dir / "pool_universe_report_v1.json")
    universe_cells = universe.get("cells_total", 0)
    if not universe:
        evidence_ok = False
        key_notes.append("MISSING_REPORT:pool_universe")
    
    # 3. Intents
    intents = _read_json_safe(reports_dir / "pool_intents_report_v1.json")
    intents_created = intents.get("intents_created", 0)
    skipped_reasons_count = intents.get("skipped_reasons_count", {})
    if not intents:
        evidence_ok = False
        key_notes.append("MISSING_REPORT:pool_intents")
    
    # 4. Selection
    selection = _read_json_safe(reports_dir / "pool_selection_report_v1.json")
    selected_count = selection.get("selected_count", 0)
    if not selection:
        evidence_ok = False
        key_notes.append("MISSING_REPORT:pool_selection")
    
    # 5. Risk
    # 5. Risk (Phase 6A.3: Priority V2, Fallback V1)
    risk_v2_path = reports_dir / "pool_risk_report_v2.json"
    risk_v1_path = reports_dir / "pool_risk_report_v1.json"
    
    blocked_reasons_count = {}
    limits = {}
    allowed_count = 0
    blocked_count = 0
    kill_switch_triggered = False
    
    if risk_v2_path.exists():
        risk_data = _read_json_safe(risk_v2_path)
        blocked_reasons_count = risk_data.get("blocked_reasons_count", {})
        limits = risk_data.get("limits", {})
        allowed_count = risk_data.get("allowed_count", 0)
        blocked_count = risk_data.get("blocked_count", 0)
        kill_switch_triggered = risk_data.get("kill_switch", {}).get("triggered", False)
    elif risk_v1_path.exists():
        risk_data = _read_json_safe(risk_v1_path)
        allowed_count = risk_data.get("allowed_count", 0)
        blocked_count = risk_data.get("blocked_count", 0)
        # Phase 5B.1 fallback
        ks_info = risk_data.get("kill_switch", {}) # Might differ in v1 structure, let's check
        # Actually V1 structure had kill_switch_triggered at root or inside?
        # Let's support both common patterns. Early phases put it at root.
        kill_switch_triggered = risk_data.get("kill_switch_triggered", False)
        if not kill_switch_triggered:
             kill_switch_triggered = risk_data.get("kill_switch", {}).get("triggered", False)
    else:
        evidence_ok = False
        key_notes.append("MISSING_REPORT:pool_risk")
    
    # 6. Execution Summary
    execution = _read_json_safe(reports_dir / "pool_execution_summary_v1.json")
    planned_orders = execution.get("planned_orders", 0)
    planned_total_notional = execution.get("planned_total_notional", 0.0)
    if not execution:
        evidence_ok = False
        key_notes.append("MISSING_REPORT:pool_execution_summary")
    
    # 7. Restart Reconcile
    reconcile = _read_json_safe(reports_dir / "restart_reconcile_report_v1.json")
    restart_reconcile_verdict = reconcile.get("verdict", "UNKNOWN")
    if not reconcile:
        evidence_ok = False
        key_notes.append("MISSING_REPORT:restart_reconcile")
    
    # 8. LIVE arm state (optional for WAR)
    if stage.lower() == "live":
        arm_state = _read_json_safe(reports_dir / "live_arm_state_report_v1.json")
        if not arm_state:
            evidence_ok = False
            key_notes.append("MISSING_REPORT:live_arm_state")
    
    return PoolJuryScorecardV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        evidence_ok=evidence_ok,
        universe_cells=universe_cells,
        intents_created=intents_created,
        selected_count=selected_count,
        allowed_count=allowed_count,
        blocked_count=blocked_count,
        planned_orders=planned_orders,
        planned_total_notional=planned_total_notional,
        restart_reconcile_verdict=restart_reconcile_verdict,
        kill_switch_triggered=kill_switch_triggered,
        blocked_reasons_count=blocked_reasons_count,
        skipped_reasons_count=skipped_reasons_count,
        limits=limits,
        key_notes=key_notes
    )
