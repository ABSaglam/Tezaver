"""
Pool Execution Runner V0
========================

Build order intents from pool reports.
"""
import json
from pathlib import Path
from typing import Dict, Any, List, Set

from tezaver.matrix.pool_exec.pool_order_intents_v1 import (
    PoolOrderIntentV1,
    PoolOrderIntentsReportV1,
    generate_order_key,
    generate_intent_id,
    now_iso
)

def _read_json_safe(path: Path) -> Dict[str, Any]:
    """Read JSON file safely."""
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}

def build_pool_order_intents_v1(
    reports_dir: Path,
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str]
) -> PoolOrderIntentsReportV1:
    """
    Build order intents from pool reports.
    
    Args:
        reports_dir: Path to run reports directory
        stage: Run stage
        run_id: Run ID
        trace_ctx: Context for determinism
        
    Returns:
        PoolOrderIntentsReportV1
    """
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    
    # Read court verdict
    court = _read_json_safe(reports_dir / "pool_court_verdict_v1.json")
    court_verdict = court.get("verdict", "FAIL")
    
    intents: List[PoolOrderIntentV1] = []
    used_order_keys: Set[str] = set()
    
    # If court FAIL, blocked
    if court_verdict == "FAIL":
        return PoolOrderIntentsReportV1(
            run_id=run_id,
            stage=stage,
            engine_version=ev,
            data_fingerprint=df,
            config_signature=cs,
            built_ts_iso=now_iso(),
            court_verdict=court_verdict,
            intents_total=0,
            intents_open=0,
            intents_close=0,
            intents=[]
        )
    
    # Read execution summary (Phase 2C)
    exec_summary = _read_json_safe(reports_dir / "pool_execution_summary_v1.json")
    plan_items = exec_summary.get("plan", [])
    
    # Normal OPEN intents from execution plan
    for item in plan_items:
        if item.get("action") == "PLACE_ORDER":
            symbol = item.get("symbol", "UNK")
            timeframe = item.get("timeframe")
            bundle_id = item.get("bundle_id")
            notional = item.get("notional", 100.0)
            policy_spec = item.get("policy_spec")
            
            order_key = generate_order_key(stage, run_id, "OPEN_POSITION", symbol, timeframe, bundle_id, "SELECTION")
            
            if order_key not in used_order_keys:
                used_order_keys.add(order_key)
                intent = PoolOrderIntentV1(
                    intent_id=generate_intent_id(order_key),
                    order_key=order_key,
                    stage=stage,
                    run_id=run_id,
                    action="OPEN_POSITION",
                    symbol=symbol,
                    timeframe=timeframe,
                    bundle_id=bundle_id,
                    src="SELECTION",
                    notional=notional,
                    mode="MARKET_SIM",
                    policy_spec=policy_spec,
                    reason="OK",
                    created_ts_iso=now_iso(),
                    meta={"from": "execution_summary"}
                )
                intents.append(intent)
    
    # Replacement plan (Phase 3C)
    replacement_plan = _read_json_safe(reports_dir / "pool_replacement_plan_v1.json")
    if replacement_plan.get("replacement_verdict") == "SUGGESTED":
        close_plan = replacement_plan.get("close_plan")
        open_plan = replacement_plan.get("open_plan")
        
        # CLOSE intent
        if close_plan:
            pos_id = close_plan.get("pos_id", "UNK")
            symbol = close_plan.get("symbol", "UNK")
            
            order_key = generate_order_key(stage, run_id, "CLOSE_POSITION", symbol, None, None, "REPLACEMENT_PLAN")
            
            if order_key not in used_order_keys:
                used_order_keys.add(order_key)
                intent = PoolOrderIntentV1(
                    intent_id=generate_intent_id(order_key),
                    order_key=order_key,
                    stage=stage,
                    run_id=run_id,
                    action="CLOSE_POSITION",
                    symbol=symbol,
                    timeframe=None,
                    bundle_id=None,
                    src="REPLACEMENT_PLAN",
                    notional=0.0,  # N/A for close
                    mode="MARKET_SIM",
                    policy_spec=None,
                    reason="REPLACEMENT_CLOSE",
                    created_ts_iso=now_iso(),
                    meta={"pos_id": pos_id}
                )
                intents.append(intent)
        
        # OPEN intent (replacement)
        if open_plan:
            symbol = open_plan.get("symbol", "UNK")
            timeframe = open_plan.get("timeframe")
            bundle_id = open_plan.get("bundle_id")
            notional = open_plan.get("notional", 100.0)
            policy_spec = open_plan.get("policy_spec")
            
            order_key = generate_order_key(stage, run_id, "OPEN_POSITION", symbol, timeframe, bundle_id, "REPLACEMENT_PLAN")
            
            if order_key not in used_order_keys:
                used_order_keys.add(order_key)
                intent = PoolOrderIntentV1(
                    intent_id=generate_intent_id(order_key),
                    order_key=order_key,
                    stage=stage,
                    run_id=run_id,
                    action="OPEN_POSITION",
                    symbol=symbol,
                    timeframe=timeframe,
                    bundle_id=bundle_id,
                    src="REPLACEMENT_PLAN",
                    notional=notional,
                    mode="MARKET_SIM",
                    policy_spec=policy_spec,
                    reason="REPLACEMENT_OPEN",
                    created_ts_iso=now_iso(),
                    meta={"from": "replacement_plan"}
                )
                intents.append(intent)
    
    intents_open = sum(1 for i in intents if i.action == "OPEN_POSITION")
    intents_close = sum(1 for i in intents if i.action == "CLOSE_POSITION")
    
    return PoolOrderIntentsReportV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        court_verdict=court_verdict,
        intents_total=len(intents),
        intents_open=intents_open,
        intents_close=intents_close,
        intents=intents
    )
