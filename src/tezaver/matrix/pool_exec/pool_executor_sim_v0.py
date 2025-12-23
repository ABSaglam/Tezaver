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
    trace_ctx: Dict[str, str]
) -> Dict[str, Any]:
    """
    Execute intents in SIM mode (no real API calls).
    
    Args:
        intents_report: Order intents report
        reports_dir: Path to reports directory
        trace_ctx: Context for determinism
        
    Returns:
        Execution result dict
    """
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    
    per_intent_status: List[Dict[str, Any]] = []
    executed_count = 0
    
    for intent in intents_report.intents:
        # SIM: Just mark as executed
        status = {
            "intent_id": intent.intent_id,
            "order_key": intent.order_key,
            "action": intent.action,
            "symbol": intent.symbol,
            "sim_status": "EXECUTED_SIM",
            "sim_ts_iso": now_iso()
        }
        per_intent_status.append(status)
        executed_count += 1
        
        # TODO: Emit telemetry SIM_ORDER_PLANNED, SIM_ORDER_ACK, SIM_ORDER_DONE
    
    result = {
        "run_id": intents_report.run_id,
        "stage": intents_report.stage,
        "engine_version": ev,
        "data_fingerprint": df,
        "config_signature": cs,
        "built_ts_iso": now_iso(),
        "mode": "SIM",
        "planned": intents_report.intents_total,
        "executed_sim": executed_count,
        "failed_sim": 0,
        "per_intent_status": per_intent_status
    }
    
    # Write result
    result_path = reports_dir / "pool_execution_sim_result_v0.json"
    write_json(result_path, result)
    
    return {
        "status": "OK",
        "result_path": str(result_path),
        "planned": intents_report.intents_total,
        "executed_sim": executed_count
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
