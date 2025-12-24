"""
Pool Court Runner V1
====================

Orchestrates Jury and Judge to produce final verdict.
"""
import json
from pathlib import Path
from typing import Dict, Any

from tezaver.matrix.pool_court.pool_jury_v1 import build_pool_scorecard
from tezaver.matrix.pool_court.pool_judge_v1 import judge_pool

def resolve_reports_dir(stage: str, run_id: str, home_dir: str = None) -> Path:
    """Resolve reports directory path."""
    base = Path(home_dir) if home_dir else Path("out/matrix_runs")
    return base / stage / run_id / "reports"

def write_report_json(path: Path, data: Dict[str, Any]):
    """Write JSON report safely."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def run_pool_court(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    home_dir: str = None
) -> Dict[str, Any]:
    """
    Run the Pool Court: build scorecard, judge, write reports.
    
    Args:
        stage: Run stage
        run_id: Run ID
        trace_ctx: {"engine_version":..., "data_fingerprint":..., "config_signature":...}
        home_dir: Optional custom home directory
        
    Returns:
        {"verdict": str, "scorecard_path": str, "verdict_path": str, ...}
    """
    reports_dir = resolve_reports_dir(stage, run_id, home_dir)
    
    # 1. Build Scorecard
    scorecard = build_pool_scorecard(reports_dir, stage, run_id, trace_ctx)
    
    # Build evidence paths
    evidence_paths = {}
    for name in [
        "pool_mode_v1.json",
        "pool_universe_report_v1.json",
        "pool_intents_report_v1.json",
        "pool_selection_report_v1.json",
        "pool_risk_report_v1.json",
        "pool_execution_summary_v1.json",
        "restart_reconcile_report_v1.json",
        "live_arm_state_report_v1.json"
    ]:
        p = reports_dir / name
        if p.exists():
            evidence_paths[name] = str(p)
    
    # 2. Judge
    verdict = judge_pool(scorecard, trace_ctx, evidence_paths)
    
    # 3. Write Reports
    scorecard_path = reports_dir / "pool_scorecard_v1.json"
    verdict_path = reports_dir / "pool_court_verdict_v1.json"
    
    write_report_json(scorecard_path, scorecard.to_dict())
    write_report_json(verdict_path, verdict.to_dict())
    
    # TODO: Emit telemetry POOL_COURT_JURY_BUILT, POOL_COURT_VERDICT
    
    return {
        "status": "OK",
        "verdict": verdict.verdict,
        "decision_action": verdict.decision_action,
        "scorecard_path": str(scorecard_path),
        "verdict_path": str(verdict_path),
        "reports_dir": str(reports_dir)
    }
