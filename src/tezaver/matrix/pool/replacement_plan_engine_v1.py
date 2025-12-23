"""
Replacement Plan Engine V1
==========================

Build atomic Close/Open plan for replacement suggestions.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from tezaver.matrix.pool.pool_models_v1 import (
    PoolClosePlanItemV1,
    PoolOpenPlanItemV1,
    PoolReplacementPlanReportV1
)

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

def build_replacement_plan(
    run_id: str,
    stage: str,
    trace_ctx: Dict[str, str],
    replacement_report: Dict[str, Any],
    reconcile_report: Dict[str, Any],
    bundle_registry = None,
    config: Optional[Dict[str, Any]] = None
) -> PoolReplacementPlanReportV1:
    """
    Build atomic replacement plan from replacement report.
    
    Args:
        run_id: Run ID
        stage: Run stage
        trace_ctx: Context for determinism
        replacement_report: Phase 3B replacement report
        reconcile_report: Phase 2D reconcile report
        bundle_registry: Bundle registry (for policy_spec lookup)
        config: {"default_notional": float}
        
    Returns:
        PoolReplacementPlanReportV1
    """
    cfg = config or {}
    default_notional = cfg.get("default_notional", 100.0)
    enabled = replacement_report.get("enabled", False)
    
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    
    base = {
        "run_id": run_id,
        "stage": stage,
        "engine_version": ev,
        "data_fingerprint": df,
        "config_signature": cs,
        "built_ts_iso": now_iso(),
        "enabled": enabled,
        "requires_human_confirm": True,
        "atomic_order": ["CLOSE_POSITION", "OPEN_POSITION"]
    }
    
    replacement_verdict = replacement_report.get("verdict", "NONE")
    
    # 1. Check if replacement not suggested
    if replacement_verdict != "SUGGESTED":
        return PoolReplacementPlanReportV1(
            **base,
            replacement_verdict=replacement_verdict,
            close_plan=None,
            open_plan=None,
            skip_reason="NO_REPLACEMENT"
        )
    
    # 2. Check reconcile drift
    reconcile_verdict = reconcile_report.get("verdict", "UNKNOWN")
    if reconcile_verdict != "OK":
        return PoolReplacementPlanReportV1(
            **base,
            replacement_verdict=replacement_verdict,
            close_plan=None,
            open_plan=None,
            skip_reason="DRIFT"
        )
    
    # 3. Get candidate
    candidate = replacement_report.get("candidate", {})
    if not candidate:
        return PoolReplacementPlanReportV1(
            **base,
            replacement_verdict=replacement_verdict,
            close_plan=None,
            open_plan=None,
            skip_reason="NO_CANDIDATE"
        )
    
    # 4. Build close plan
    close_plan = PoolClosePlanItemV1(
        action="CLOSE_POSITION",
        pos_id=candidate.get("replace_out_pos_id", "UNK"),
        symbol=candidate.get("replace_out_symbol", "UNK"),
        close_mode="MARKET_DRYRUN",
        reason="REPLACEMENT_WORSE_THAN_NEW",
        notes=["atomic_replacement", "dry_run"]
    )
    
    # 5. Build open plan
    bundle_id = candidate.get("replace_in_bundle_id")
    policy_spec = None
    if bundle_registry and bundle_id:
        bundle = bundle_registry.get(bundle_id)
        if bundle and bundle.manifest:
            policy_spec = getattr(bundle.manifest, "policy_spec_v1", None)
    
    open_plan = PoolOpenPlanItemV1(
        action="OPEN_POSITION",
        intent_id=candidate.get("replace_in_intent_id", "UNK"),
        bundle_id=bundle_id or "UNK",
        symbol=candidate.get("replace_in_symbol", "UNK"),
        timeframe=candidate.get("replace_in_timeframe", "UNK"),
        notional=default_notional,
        open_mode="MARKET_DRYRUN",
        policy_spec=policy_spec,
        notes=["atomic_replacement", "dry_run", "requires_human_confirm"]
    )
    
    return PoolReplacementPlanReportV1(
        **base,
        replacement_verdict=replacement_verdict,
        close_plan=close_plan,
        open_plan=open_plan,
        skip_reason=None
    )
