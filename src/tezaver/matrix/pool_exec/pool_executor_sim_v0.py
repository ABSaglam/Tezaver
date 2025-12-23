"""
Pool Executor SIM V0
====================

Simulated execution (no real orders).
"""
import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

from tezaver.matrix.pool_exec.pool_order_intents_v1 import PoolOrderIntentsReportV1

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def write_json(path: Path, data: Dict[str, Any]):
    """Write JSON safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def run_sim_execution(
    intents_report: PoolOrderIntentsReportV1,
    reports_dir: Path,
    trace_ctx: Dict[str, str],
    home_dir: str = None
) -> Dict[str, Any]:
    """
    Execute intents in SIM mode (no real API calls).
    
    Args:
        intents_report: Order intents report
        reports_dir: Path to reports directory
        trace_ctx: Context for determinism
        home_dir: Optional home directory for idempotency store
        
    Returns:
        Execution result dict
    """
    from tezaver.matrix.pool_exec.idempotency_store_v1 import has_key, add_key, keys_count
    
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    
    stage = intents_report.stage
    run_id = intents_report.run_id
    
    per_intent_status: List[Dict[str, Any]] = []
    executed_count = 0
    skipped_idempotent = 0
    sample_blocked: List[Dict[str, str]] = []
    fills = []  # Phase 6A.1: Fill results
    
    for intent in intents_report.intents:
        order_key = intent.order_key
        
        # Check idempotency
        if has_key(stage, run_id, order_key, home_dir):
            # SKIPPED_IDEMPOTENT
            status = {
                "intent_id": intent.intent_id,
                "order_key": order_key,
                "action": intent.action,
                "symbol": intent.symbol,
                "sim_status": "SKIPPED_IDEMPOTENT",
                "sim_ts_iso": now_iso()
            }
            per_intent_status.append(status)
            skipped_idempotent += 1
            
            if len(sample_blocked) < 5:
                sample_blocked.append({
                    "order_key": order_key,
                    "intent_id": intent.intent_id,
                    "action": intent.action,
                    "symbol": intent.symbol
                })
            # TODO: emit telemetry IDEMPOTENCY_BLOCKED
        else:
            # Execute SIM with fill simulation
            from tezaver.matrix.pool_exec.sim_fill_model_v1 import (
                simulate_fill, DEFAULT_FEE_BPS, DEFAULT_SLIPPAGE_BPS
            )
            
            # Get fee/slippage from policy_spec or defaults
            policy_spec = intent.policy_spec or {}
            fee_bps = policy_spec.get("fee_bps", DEFAULT_FEE_BPS)
            slippage_bps = policy_spec.get("slippage_bps", DEFAULT_SLIPPAGE_BPS)
            
            # Reference price: from meta or default 1.0
            ref_price = intent.meta.get("ref_price", 1.0) if intent.meta else 1.0
            
            # Simulate fill
            fill = simulate_fill(
                order_key=order_key,
                intent_id=intent.intent_id,
                action=intent.action,
                symbol=intent.symbol,
                timeframe=intent.timeframe,
                ref_price=ref_price,
                notional=intent.notional,
                fee_bps=fee_bps,
                slippage_bps=slippage_bps
            )
            fills.append(fill)
            
            status = {
                "intent_id": intent.intent_id,
                "order_key": order_key,
                "action": intent.action,
                "symbol": intent.symbol,
                "sim_status": "EXECUTED_SIM",
                "sim_ts_iso": now_iso(),
                "eff_price": fill.eff_price,
                "fee_cost": fill.fee_cost,
                "slippage_cost": fill.slippage_cost
            }
            per_intent_status.append(status)
            executed_count += 1
            
            # Add key to store
            add_key(stage, run_id, order_key, home_dir)
            # TODO: emit telemetry IDEMPOTENCY_KEY_ADDED
    
    # Compute totals
    total_fee_cost = sum(f.fee_cost for f in fills)
    total_slippage_cost = sum(f.slippage_cost for f in fills)
    
    result = {
        "run_id": run_id,
        "stage": stage,
        "engine_version": ev,
        "data_fingerprint": df,
        "config_signature": cs,
        "built_ts_iso": now_iso(),
        "mode": "SIM",
        "planned": intents_report.intents_total,
        "executed_sim": executed_count,
        "skipped_idempotent": skipped_idempotent,
        "failed_sim": 0,
        "per_intent_status": per_intent_status,
        "total_fee_cost": total_fee_cost,
        "total_slippage_cost": total_slippage_cost
    }
    
    # Write result
    result_path = reports_dir / "pool_execution_sim_result_v0.json"
    write_json(result_path, result)
    
    # Write idempotency report
    keys_total_after = keys_count(stage, run_id, home_dir)
    idemp_report = {
        "run_id": run_id,
        "stage": stage,
        "built_ts_iso": now_iso(),
        "total_intents": intents_report.intents_total,
        "executed_sim": executed_count,
        "skipped_idempotent": skipped_idempotent,
        "keys_total_after": keys_total_after,
        "sample_blocked": sample_blocked
    }
    idemp_path = reports_dir / "pool_idempotency_report_v1.json"
    write_json(idemp_path, idemp_report)
    
    # Write fill report (Phase 6A.1)
    from tezaver.matrix.pool_exec.sim_fill_model_v1 import DEFAULT_FEE_BPS, DEFAULT_SLIPPAGE_BPS
    fill_report = {
        "run_id": run_id,
        "stage": stage,
        "mode": "SIM",
        "defaults": {"fee_bps": DEFAULT_FEE_BPS, "slippage_bps": DEFAULT_SLIPPAGE_BPS},
        "fills_total": len(fills),
        "fills": [f.to_dict() for f in fills],
        "totals": {"fee_cost": total_fee_cost, "slippage_cost": total_slippage_cost}
    }
    fill_path = reports_dir / "pool_sim_fill_report_v1.json"
    write_json(fill_path, fill_report)
    
    return {
        "status": "OK",
        "result_path": str(result_path),
        "planned": intents_report.intents_total,
        "executed_sim": executed_count,
        "skipped_idempotent": skipped_idempotent,
        "total_fee_cost": total_fee_cost,
        "total_slippage_cost": total_slippage_cost
    }


def run_pool_execution_sim_v0(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    reports_dir: Path
) -> Dict[str, Any]:
    """
    Full execution pipeline: build intents + run SIM.
    
    Args:
        stage: Run stage
        run_id: Run ID
        trace_ctx: Context for determinism
        reports_dir: Path to reports directory
        
    Returns:
        Summary dict
    """
    from tezaver.matrix.pool_exec.pool_execution_runner_v0 import build_pool_order_intents_v1
    
    # Build intents
    intents_report = build_pool_order_intents_v1(reports_dir, stage, run_id, trace_ctx)
    
    # Write intents report
    intents_path = reports_dir / "pool_order_intents_v1.json"
    write_json(intents_path, intents_report.to_dict())
    
    # Run SIM
    sim_result = run_sim_execution(intents_report, reports_dir, trace_ctx)
    
    return {
        "status": "OK",
        "intents_path": str(intents_path),
        "sim_result": sim_result,
        "court_verdict": intents_report.court_verdict,
        "intents_total": intents_report.intents_total
    }
