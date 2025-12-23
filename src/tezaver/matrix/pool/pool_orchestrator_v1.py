"""
Pool Orchestrator V1
====================

Single-command orchestration of all Pool phases (2A→2D) for evidence generation.
"""
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from tezaver.matrix.bundles.bundle_registry import BundleRegistry
from tezaver.matrix.pool.pool_reports_v1 import resolve_reports_dir, write_report_json, now_iso
from tezaver.matrix.pool.portfolio_provider_v1 import StubPortfolioProviderV1
from tezaver.matrix.pool.reconcile_provider_v1 import StubOpenPositionsProviderV1
from tezaver.matrix.pool.pool_engine_v1 import (
    run_pool_phase2a,
    run_pool_phase2b,
    run_pool_phase2c,
    run_pool_phase2d_live_arm,
    run_pool_phase2d_restart_reconcile
)


def write_pool_mode_marker(stage: str, run_id: str, pool_enabled: bool = True) -> Path:
    """
    Write pool_mode_v1.json marker to indicate pool_enabled status.
    
    Args:
        stage: Run stage
        run_id: Run ID
        pool_enabled: Whether pool is enabled
        
    Returns:
        Path to marker file
    """
    reports_dir = resolve_reports_dir(stage, run_id)
    marker = {
        "pool_enabled": pool_enabled,
        "ts": now_iso(),
        "run_id": run_id,
        "stage": stage
    }
    path = reports_dir / "pool_mode_v1.json"
    write_report_json(path, marker)
    return path


def run_pool_evidence_bundle(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    registry: BundleRegistry,
    options: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute all Pool phases (2A→2D) to generate complete evidence bundle.
    
    Args:
        stage: Run stage ("war" or "live")
        run_id: Run ID
        trace_ctx: {"engine_version":..., "data_fingerprint":..., "config_signature":...}
        registry: Bundle registry with loaded bundles
        options: {
            "kill_switch_triggered": bool (default False),
            "risk_limiter_triggered": bool (default False),
            "max_open_positions": int (default 20),
            "closed_bars": dict (optional)
        }
        
    Returns:
        Summary dict with all paths and status
    """
    opts = options or {}
    kill_switch = opts.get("kill_switch_triggered", False)
    risk_limiter = opts.get("risk_limiter_triggered", False)
    max_positions = opts.get("max_open_positions", 20)
    global_limits = opts.get("global_limits")
    closed_bars = opts.get("closed_bars", {"15m": now_iso(), "1h": now_iso(), "4h": now_iso()})
    
    results = {"stage": stage, "run_id": run_id, "phases": {}}
    
    # Write pool_enabled marker
    marker_path = write_pool_mode_marker(stage, run_id, pool_enabled=True)
    results["pool_mode_marker"] = str(marker_path)
    
    # Phase 2A: Universe, Tick, Intents
    res_2a = run_pool_phase2a(stage, run_id, registry, trace_ctx, closed_bars)
    results["phases"]["2a"] = res_2a
    intents_list = res_2a.get("intents_list", [])
    
    # Phase 2B: Portfolio Snapshot & Selection
    portfolio_provider = StubPortfolioProviderV1(open_positions=[])
    res_2b = run_pool_phase2b(stage, run_id, trace_ctx, intents_list, portfolio_provider, max_positions)
    results["phases"]["2b"] = res_2b
    selected_items = res_2b.get("selected_items", [])
    
    # Phase 2C: Risk & Execution Plan (DRY-RUN)
    res_2c = run_pool_phase2c(
        stage, run_id, trace_ctx, selected_items, registry,
        global_limits=global_limits,
        kill_switch_triggered=kill_switch,
        risk_limiter_triggered=risk_limiter
    )
    results["phases"]["2c"] = res_2c
    
    # Phase 2D: Restart Reconcile (always)
    before_provider = StubOpenPositionsProviderV1([])
    after_provider = StubOpenPositionsProviderV1([])
    res_2d_reconcile = run_pool_phase2d_restart_reconcile(stage, run_id, trace_ctx, before_provider, after_provider)
    results["phases"]["2d_reconcile"] = res_2d_reconcile
    
    # Phase 2D: LIVE Arm State (only for LIVE stage)
    if stage.lower() == "live":
        # For evidence, we create an armed state with the first selected bundle
        arm_state = {
            "armed": True,
            "arm_reason": "BUNDLE_ARMED",
            "bundle_id": selected_items[0].bundle_id if selected_items else None,
            "symbol": selected_items[0].symbol if selected_items else None,
            "timeframe": selected_items[0].timeframe if selected_items else None,
            "qc_score": selected_items[0].qc_score if selected_items else None,
            "tier": selected_items[0].tier if selected_items else None,
            "notes": ["evidence_bundle"]
        }
        res_2d_arm = run_pool_phase2d_live_arm(stage, run_id, trace_ctx, arm_state)
        results["phases"]["2d_live_arm"] = res_2d_arm
    
    results["status"] = "OK"
    results["reports_dir"] = str(resolve_reports_dir(stage, run_id))
    
    return results
