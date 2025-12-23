"""
Pool Engine V1
==============

Core implementation of the Pool Engine Kernel (Phase 2A).
Orchestrates Universe building, Tick processing, and Intent generation.
"""
import hashlib
from typing import List, Dict, Optional, Any, Tuple
from collections import defaultdict

from tezaver.matrix.bundles.bundle_registry import BundleRegistry
from tezaver.matrix.pool.pool_models_v1 import (
    PoolUniverseCellV1,
    PoolUniverseReportV1,
    PoolTickReportV1,
    TradeIntentV1,
    PoolIntentsReportV1,
    PoolPortfolioSnapshotV1,
    PoolSelectionReportV1
)
from tezaver.matrix.pool.pool_reports_v1 import (
    resolve_reports_dir,
    write_report_json,
    now_iso
)
from tezaver.matrix.pool.portfolio_provider_v1 import PortfolioProviderV1
from tezaver.matrix.pool.pool_selector_v1 import select_topk

def build_universe_from_bundle_registry(registry: BundleRegistry) -> List[PoolUniverseCellV1]:
    """
    Build the pool universe from loaded bundles given in the registry.
    Groups bundles by symbol and timeframe, selecting the best (highest QC score) for each cell.
    
    Args:
        registry: Populated BundleRegistry
        
    Returns:
        List of PoolUniverseCellV1
    """
    # Group by (symbol, timeframe)
    cells_map = defaultdict(list)
    loaded_bundles = registry.list_loaded_bundles()
    
    for b in loaded_bundles:
        if b.status == "LOADED_OK" and b.manifest:
            key = (b.manifest.symbol, b.manifest.timeframe)
            cells_map[key].append(b)
            
    universe_cells = []
    
    for (symbol, tf), bundles in cells_map.items():
        # Find best bundle (max QC score)
        best_bundle = None
        max_score = -1
        
        bundle_ids = []
        for b in bundles:
            bundle_ids.append(b.manifest.bundle_id)
            if b.manifest.qc_score > max_score:
                max_score = b.manifest.qc_score
                best_bundle = b
        
        # Create cell
        cell = PoolUniverseCellV1(
            symbol=symbol,
            timeframe=tf,
            bundles_loaded_ok=bundle_ids,
            best_bundle_id=best_bundle.manifest.bundle_id if best_bundle else None,
            qc_score_best=best_bundle.manifest.qc_score if best_bundle else None,
            tier_best=best_bundle.manifest.tier if best_bundle else None
        )
        universe_cells.append(cell)
        
    return universe_cells

def _generate_intent_id(symbol: str, tf: str, bundle_id: str, tick_ts: str, trigger: str, policy: str) -> str:
    """Generate deterministic Intent ID."""
    raw = f"{symbol}|{tf}|{bundle_id}|{tick_ts}|{trigger}|{policy}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def build_intents(
    universe_cells: List[PoolUniverseCellV1],
    tick_ts_iso: str,
    closed_bars: Dict[str, str], # timeframe -> bar_ts_iso
    registry: BundleRegistry
) -> Tuple[List[TradeIntentV1], Dict[str, int]]:
    """
    Generate trade intents for the current tick based on the universe and closed bars.
    
    Args:
        universe_cells: Active pool universe
        tick_ts_iso: Current tick timestamp
        closed_bars: Map of closed bars (e.g. {"1h": "2023-01-01T10:00:00Z"})
        registry: Bundle registry to look up specs
        
    Returns:
        (List[TradeIntentV1], skipped_counts_dict)
    """
    intents = []
    skipped_reasons = defaultdict(int)
    
    for cell in universe_cells:
        # 1. Check if cell's timeframe has a closed bar in this tick
        #    If not, we might still process it? Prompt says "Closed-bar Tick".
        #    Usually we only trigger if the TF bar just closed.
        #    The prompt says "Closed-bar only: Tick sadece BAR_CLOSED ile çalışır."
        #    Let's assume we check if cell.timeframe is in closed_bars.
        
        if cell.timeframe not in closed_bars:
            # Not a trigger moment for this cell
            # We don't counting this as skipped in the intent report usually, or do we?
            # "intents_skipped" usually refers to logic failures (missing specs etc.)
            continue
            
        # 2. Check best bundle
        if not cell.best_bundle_id:
            skipped_reasons["NO_BEST_BUNDLE"] += 1
            continue
            
        bundle = registry.get(cell.best_bundle_id)
        if not bundle or not bundle.manifest:
            skipped_reasons["BUNDLE_NOT_FOUND"] += 1
            continue
            
        m = bundle.manifest
        
        # 3. Check V2 Specs
        trigger = m.trigger_spec_v1
        policy = m.policy_spec_v1
        
        if not trigger or not policy:
            reason = "SKIPPED_NO_SPECS"
            if not trigger: reason = "SKIPPED_NO_TRIGGER"
            if not policy: reason = "SKIPPED_NO_POLICY"
            if not trigger and not policy: reason = "SKIPPED_NO_SPECS"
            
            # Record failed/skipped intent
            # We still create an intent object to record decision, but with reason != OK
            # Wait, TradeIntentV1 has a reason field.
            # "intent yine kayda girebilir ama created sayılmasın."
            
            # Generate ID for tracking even if skipped
            intent_id = _generate_intent_id(
                m.symbol, m.timeframe, m.bundle_id, tick_ts_iso, 
                "NONE", "NONE"
            )
            
            intent = TradeIntentV1(
                intent_id=intent_id,
                symbol=m.symbol,
                timeframe=m.timeframe,
                bundle_id=m.bundle_id,
                trigger_type="NONE",
                exit_policy="NONE",
                created_ts_iso=now_iso(),
                reason=reason,
                qc_score=m.qc_score,
                tier=m.tier
            )
            intents.append(intent)
            skipped_reasons[reason] += 1
            continue
            
        # 4. Create Valid Intent
        trigger_type = trigger.get("type", "UNKNOWN")
        exit_policy = policy.get("exit_policy", "UNKNOWN")
        
        intent_id = _generate_intent_id(
            m.symbol, m.timeframe, m.bundle_id, tick_ts_iso, 
            trigger_type, exit_policy
        )
        
        intent = TradeIntentV1(
            intent_id=intent_id,
            symbol=m.symbol,
            timeframe=m.timeframe,
            bundle_id=m.bundle_id,
            trigger_type=trigger_type,
            exit_policy=exit_policy,
            created_ts_iso=now_iso(),
            reason="OK",
            qc_score=m.qc_score,
            tier=m.tier,
            entry_ts_iso=None # Pending execution
        )
        intents.append(intent)
        
    return intents, skipped_reasons

def run_pool_phase2a(
    stage: str,
    run_id: str,
    registry: BundleRegistry,
    trace_ctx: Dict[str, str],
    closed_bars_input: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Execute Pool Phase 2A: Build Universe, Tick, and Intents.
    Writes 3 reports.
    
    Args:
        stage: Run stage
        run_id: Run ID
        registry: Bundle registry
        trace_ctx: {"engine_version":..., "data_fingerprint":..., "config_signature":...}
        closed_bars_input: Optional dict of closed bars for this tick
        
    Returns:
        Summary dict with paths and counts
    """
    # 0. Context
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    reports_dir = resolve_reports_dir(stage, run_id)
    
    # 1. Build Universe
    universe_cells = build_universe_from_bundle_registry(registry)
    
    cells_by_tf = defaultdict(int)
    for c in universe_cells:
        cells_by_tf[c.timeframe] += 1
        
    uni_report = PoolUniverseReportV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        cells_total=len(universe_cells),
        cells_by_tf=dict(cells_by_tf),
        cells=universe_cells
    )
    
    write_report_json(reports_dir / "pool_universe_report_v1.json", uni_report.to_dict())
    
    # 2. Tick
    tick_ts = now_iso()
    closed_bars = closed_bars_input or {}
    
    # 3. Intents
    intents, skipped_reasons = build_intents(universe_cells, tick_ts, closed_bars, registry)
    
    created_count = sum(1 for i in intents if i.reason == "OK")
    skipped_count = len(intents) - created_count
    
    # Write Tick Report
    tick_report = PoolTickReportV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        tick_ts_iso=tick_ts,
        tick_reason="BAR_CLOSED",
        closed_bars=closed_bars,
        intents_considered=len(universe_cells), # Only if we check all cells? 
                                              # Actually logic above filters by closed_bars.
                                              # Let's say considered = cells triggered by closed bar?
                                              # But build_intents returns only those.
                                              # "intents_considered" might mean potential candidates.
        intents_created=created_count,
        intents_skipped=skipped_count
    )
    # Refine intents_considered: actually len(intents) includes both created and skipped.
    # But skipped_reasons only track logic skips (no specs).
    # If timeframe mismatch, it's not in the list.
    # So intents_considered = len(intents) is roughly correct for "active cells in this tick".
    tick_report.intents_considered = len(intents)
    
    write_report_json(reports_dir / "pool_tick_report_v1.json", tick_report.to_dict())
    
    # Write Intents Report
    intents_report = PoolIntentsReportV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        intents_total=len(intents),
        intents_created=created_count,
        intents_skipped=skipped_count,
        intents=intents,
        skipped_reasons_count=dict(skipped_reasons)
    )
    
    write_report_json(reports_dir / "pool_intents_report_v1.json", intents_report.to_dict())
    
    return {
        "status": "OK",
        "reports_dir": str(reports_dir),
        "universe_cells": len(universe_cells),
        "intents_created": created_count,
        "intents_list": intents # Pass for Phase 2B
    }

def run_pool_phase2b(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    intents_input: List[TradeIntentV1],
    portfolio_provider: PortfolioProviderV1,
    max_open_positions: int = 20
) -> Dict[str, Any]:
    """
    Execute Pool Phase 2B: Portfolio Snapshot & Deterministic Selection.
    
    Args:
        stage: Run stage
        run_id: Run ID
        trace_ctx: Context for determinism
        intents_input: List of generated intents from Phase 2A
        portfolio_provider: Provider for current state
        max_open_positions: Global capacity limit
        
    Returns:
        Summary dict
    """
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    reports_dir = resolve_reports_dir(stage, run_id)
    
    # 1. Portfolio Snapshot
    open_positions = portfolio_provider.get_open_positions()
    open_now = len(open_positions)
    # Capacity Rule: Max(0, LIMIT - OPEN)
    capacity = max(0, max_open_positions - open_now)
    
    snapshot_report = PoolPortfolioSnapshotV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        max_open_positions=max_open_positions,
        open_now=open_now,
        capacity=capacity,
        open_positions=open_positions,
        source=portfolio_provider.get_source_name()
    )
    
    write_report_json(reports_dir / "pool_portfolio_snapshot_v1.json", snapshot_report.to_dict())
    
    # 2. Filter Eligible Intents
    intents_ok = [i for i in intents_input if i.reason == "OK"]
    
    # Track reasons for non-OK ones
    skipped_reasons = defaultdict(int)
    non_eligible_skipped = []
    
    for i in intents_input:
        if i.reason != "OK":
            skipped_reasons[i.reason] += 1
            non_eligible_skipped.append({"intent_id": i.intent_id, "reason": i.reason})
            
    # 3. Selection (Top-K)
    selected_items, overflow_skipped = select_topk(intents_ok, capacity)
    
    # Aggregate skipped
    if overflow_skipped:
        skipped_reasons["SKIPPED_OVERFLOW"] += len(overflow_skipped)
        
    all_skipped = non_eligible_skipped + overflow_skipped
    
    selection_report = PoolSelectionReportV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        max_open_positions=max_open_positions,
        open_now=open_now,
        capacity=capacity,
        intents_considered=len(intents_input),
        intents_eligible=len(intents_ok),
        selected_count=len(selected_items),
        skipped_count=len(all_skipped),
        skipped_reasons_count=dict(skipped_reasons),
        selected=selected_items,
        skipped=all_skipped,
        selection_policy_v1={
            "algorithm": "TOPK",
            "score": "qc+tier",
            "tiebreak": "intent_id",
            "replacement_enabled": False
        }
    )
    
    write_report_json(reports_dir / "pool_selection_report_v1.json", selection_report.to_dict())
    
    return {
        "status": "OK",
        "reports_dir": str(reports_dir),
        "capacity": capacity,
        "selected": len(selected_items)
    }
