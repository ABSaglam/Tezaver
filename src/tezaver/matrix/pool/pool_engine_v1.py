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
from tezaver.matrix.pool.pool_risk_limiter_v1 import DEFAULT_NOTIONAL_PER_TRADE
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

from tezaver.matrix.sniper.certification_registry import CertificationRegistry, STAGE_CANDIDATE



from tezaver.matrix.sniper.certification_registry import CertificationRegistry, STAGE_SNIPER_PASSED, STAGE_LIVE_CERTIFIED

class PoolDefender:
    """
    The Defender (Avukat).
    
    Role:
      - Defends Foundry Bundles.
      - Submits 'TradeIntent' to Court.
      - Checks Client Certification (Sniper Visa).
    """
    def __init__(self, registry: BundleRegistry):
        self.registry = registry
        self.cert_registry = CertificationRegistry()

    def defend(
        self,
        universe_cells: List[PoolUniverseCellV1],
        tick_ts_iso: str,
        closed_bars: Dict[str, str],
        stage: str = "WAR"
    ) -> Tuple[List[TradeIntentV1], Dict[str, int]]:
        """
        Build Intents for the current tick (The Defense).
        """
        intents = []
        skipped_reasons = defaultdict(int)
        
        for cell in universe_cells:
            if cell.timeframe not in closed_bars:
                continue
                
            if not cell.best_bundle_id:
                skipped_reasons["NO_BEST_BUNDLE"] += 1
                continue
                
            bundle = self.registry.get(cell.best_bundle_id)
            if not bundle or not bundle.manifest:
                skipped_reasons["BUNDLE_NOT_FOUND"] += 1
                continue
                
            m = bundle.manifest
            bundle_cert = self.cert_registry.get_bundle_stage(m.bundle_id)
            
            # --- DEFENSE GATE: SNIPER VISA CHECK ---
            # If in WAR mode, we demand SNIPER_PASSED (or better).
            if stage == "WAR":
                allowed_stages = [STAGE_SNIPER_PASSED, STAGE_LIVE_CERTIFIED]
                # Note: STAGE_CANDIDATE is NOT allowed in WAR.
                if bundle_cert not in allowed_stages:
                    reason = "SKIPPED_NOT_CERTIFIED"
                    self._add_skipped_intent(intents, m, tick_ts_iso, reason, bundle_cert)
                    skipped_reasons[reason] += 1
                    continue
            
            # Check Specs
            trigger = m.trigger_spec_v1
            policy = m.policy_spec_v1
            
            if not trigger or not policy:
                reason = "SKIPPED_NO_SPECS"
                if not trigger: reason = "SKIPPED_NO_TRIGGER"
                if not policy: reason = "SKIPPED_NO_POLICY"
                self._add_skipped_intent(intents, m, tick_ts_iso, reason, bundle_cert)
                skipped_reasons[reason] += 1
                continue
                
            # Create Valid Intent
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
                proposed_notional=float(policy.get("notional", DEFAULT_NOTIONAL_PER_TRADE)),
                tier=m.tier,
                entry_ts_iso=None,
                scenario_id=m.scenario_id,
                narrative=m.narrative,
                bundle_certification=bundle_cert
            )
            intents.append(intent)
            
        return intents, skipped_reasons

    def _add_skipped_intent(self, intents, m, tick_ts_iso, reason, cert):
        """Helper to record a skipped intent."""
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
            proposed_notional=0.0,
            tier=m.tier,
            entry_ts_iso=None,
            scenario_id=m.scenario_id,
            narrative=m.narrative,
            bundle_certification=cert
        )
        intents.append(intent)


def build_intents(
    universe_cells: List[PoolUniverseCellV1],
    tick_ts_iso: str,
    closed_bars: Dict[str, str],
    registry: BundleRegistry,
    stage: str = "WAR"
) -> Tuple[List[TradeIntentV1], Dict[str, int]]:
    """
    Legacy wrapper for PoolDefender.defend.
    """
    defender = PoolDefender(registry)
    return defender.defend(universe_cells, tick_ts_iso, closed_bars, stage)



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
    

    # 3. Intents (The Defense)
    # Pass 'stage' to allow PoolDefender to check Sniper Certification in WAR mode.
    intents, skipped_reasons = build_intents(universe_cells, tick_ts, closed_bars, registry, stage=stage)
    
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
    k = snapshot_report.capacity
    selected_items, selector_skipped = select_topk(intents_ok, k, engine_stage=stage)
    
    # 4. Aggregate Skips & Reasons
    for sk in selector_skipped:
        skipped_reasons[sk["reason"]] += 1
        
    all_skipped_list = non_eligible_skipped + selector_skipped
    
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
        skipped_count=len(all_skipped_list),
        skipped_reasons_count=dict(skipped_reasons),
        selected=selected_items,
        skipped=all_skipped_list,
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
        "selected": len(selected_items),
        "selected_items": selected_items  # Pass for Phase 2C
    }


def run_pool_phase2c(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    selected_items: List["PoolSelectionItemV1"],
    registry: BundleRegistry,
    global_limits: Optional[Dict[str, Any]] = None,
    kill_switch_triggered: bool = False,
    risk_limiter_triggered: bool = False
) -> Dict[str, Any]:
    """
    Execute Pool Phase 2C: Risk Evaluation & Dry-Run Execution Plan.
    NO ACTUAL ORDERS ARE PLACED.
    
    Args:
        stage: Run stage
        run_id: Run ID
        trace_ctx: Context for determinism
        selected_items: List of selected intents from Phase 2B
        registry: Bundle registry for manifest lookup
        global_limits: Risk limits configuration
        kill_switch_triggered: Emergency stop flag
        risk_limiter_triggered: Global risk limit flag
        
    Returns:
        Summary dict
    """
    from tezaver.matrix.pool.pool_models_v1 import (
        PoolSelectionItemV1,
        PoolRiskReportV1,
        PoolExecutionPlanItemV1,
        PoolExecutionSummaryV1
    )
    from tezaver.matrix.pool.pool_risk_engine_v1 import (
        evaluate_risk,
        DEFAULT_MAX_TOTAL_NOTIONAL,
        DEFAULT_PER_COIN_MAX_NOTIONAL
    )
    
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    reports_dir = resolve_reports_dir(stage, run_id)
    
    limits = global_limits or {
        "max_open_positions": 20,
        "max_total_notional": DEFAULT_MAX_TOTAL_NOTIONAL,
        "per_coin_max_notional": DEFAULT_PER_COIN_MAX_NOTIONAL
    }
    
    # --- Phase 6A.3 Wiring: Risk Limiter V1 ---
    from tezaver.matrix.pool.pool_risk_limiter_v1 import (
        apply_limits,
        build_risk_report_v2,
        DEFAULT_GLOBAL_NOTIONAL_CAP,
        DEFAULT_PER_COIN_NOTIONAL_CAP
    )
    from tezaver.matrix.pool.portfolio_provider_v2 import PortfolioProviderV2
    from tezaver.matrix.pool.pool_models_v1 import PoolRiskItemV1

    # 1. Prepare Portfolio State (V2)
    try:
        from tezaver.matrix.pool.portfolio_state_store_sim_v1 import load_state_v2
        st_v2 = load_state_v2(stage, run_id, home_dir=None)
        portfolio_open_notional = st_v2.totals.notional_open
        portfolio_open_now = st_v2.totals.open_positions
        coin_open_notional = {}
        for p in st_v2.positions:
            if p.status == "OPEN":
                sym = p.symbol
                coin_open_notional[sym] = coin_open_notional.get(sym, 0.0) + p.notional_entry
    except Exception:
        portfolio_open_notional = 0.0
        portfolio_open_now = 0
        coin_open_notional = {}

    # 2. Config Limits
    global_cap_val = limits.get("max_total_notional") or DEFAULT_GLOBAL_NOTIONAL_CAP
    per_coin_cap_val = limits.get("per_coin_max_notional") or DEFAULT_PER_COIN_NOTIONAL_CAP

    # 3. Apply Limits
    limiter_intents = []
    for item in selected_items:
        limiter_intents.append({
            "intent_id": item.intent_id,
            "symbol": item.symbol,
            "rank_score": item.rank_score,
            "notional": item.proposed_notional,
            "original_item": item 
        })
        
    limit_result = apply_limits(
        selected_intents=limiter_intents,
        portfolio_open_notional=portfolio_open_notional,
        coin_open_notional=coin_open_notional,
        global_notional_cap=global_cap_val,
        per_coin_notional_cap=per_coin_cap_val,
        kill_switch_triggered=kill_switch_triggered
    )

    # 4. Generate Reports
    # V2 Report
    ks_dict = {"triggered": kill_switch_triggered}
    
    # Clean up results for JSON report (remove original_item object)
    def _clean_for_json(items):
        clean = []
        for i in items:
            c = i.copy()
            if "original_item" in c:
                del c["original_item"]
            clean.append(c)
        return clean
        
    report_v2 = build_risk_report_v2(
        run_id=run_id,
        stage=stage,
        selected_intents=_clean_for_json(limiter_intents),
        limit_result=limit_result, # limit_result.allowed/blocked still have original_item
        portfolio_open_notional=portfolio_open_notional,
        portfolio_open_now=portfolio_open_now,
        global_notional_cap=global_cap_val,
        per_coin_notional_cap=per_coin_cap_val,
        kill_switch=ks_dict
    )
    # limit_result has raw lists with original_item, we need to clean them in the report object
    # Re-assign cleaned lists to report object
    report_v2.allowed = _clean_for_json(limit_result.allowed)
    report_v2.blocked = _clean_for_json(limit_result.blocked)
    
    write_report_json(reports_dir / "pool_risk_report_v2.json", report_v2.to_dict())

    # Map to V1 for backward compat
    allowed_items = []
    for d in limit_result.allowed:
        orig = d["original_item"]
        allowed_items.append(PoolRiskItemV1(
            intent_id=orig.intent_id,
            symbol=orig.symbol,
            timeframe=orig.timeframe,
            bundle_id=orig.bundle_id,
            # PoolRiskItemV1 does not store rank_score apparently
            qc_score=orig.qc_score,
            tier=orig.tier,
            proposed_notional=orig.proposed_notional,
            risk_units=0.0, # Dummy
            stop_type=orig.exit_policy, # Using exit_policy as stop_type
            stop_value=None,
            risk_flags=[],
            verdict="ALLOW",
            block_reason=None
        ))
        
    blocked_items = []
    for d in limit_result.blocked:
        orig = d["original_item"]
        reason = d.get("reason", "RISK_LIMIT")
        blocked_items.append(PoolRiskItemV1(
            intent_id=orig.intent_id,
            symbol=orig.symbol,
            timeframe=orig.timeframe,
            bundle_id=orig.bundle_id,
            # PoolRiskItemV1 does not store rank_score
            qc_score=orig.qc_score,
            tier=orig.tier,
            proposed_notional=orig.proposed_notional,
            risk_units=0.0,
            stop_type=orig.exit_policy,
            stop_value=None,
            risk_flags=[],
            verdict="BLOCK",
            block_reason=reason
        ))

    total_proposed = sum(i.proposed_notional for i in (allowed_items + blocked_items))
    total_allowed = sum(i.proposed_notional for i in allowed_items)
    
    risk_items_all = allowed_items + blocked_items

    risk_report_v1 = PoolRiskReportV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        selection_run_id=run_id,
        selected_count=len(selected_items),
        allowed_count=len(allowed_items),
        blocked_count=len(blocked_items),
        total_proposed_notional=total_proposed,
        total_allowed_notional=total_allowed,
        global_limits=limits,
        kill_switch={"triggered": kill_switch_triggered},
        risk_limiter={"triggered": limit_result.blocked_reasons_count.get("GLOBAL_NOTIONAL_CAP", 0) > 0},
        items=risk_items_all, # Assuming V1 uses 'items' list now
        blocked_reasons_count=limit_result.blocked_reasons_count
    )
    write_report_json(reports_dir / "pool_risk_report_v1.json", risk_report_v1.to_dict())

    # Build execution inputs for next steps (allowed/blocked list)
    # Pipeline expects these lists, so we return them or put in summary
    # The return dict below uses len() but pipeline might use these objects if we pass them.
    # Actually run_pool_pipeline pass context via return.
    # But wait, pool_execute_sim_v0.py (Phase 4) runs on intents.
    
    # 2. Execution Plan (DRY-RUN)
    plan_items: List[PoolExecutionPlanItemV1] = []
    per_tf: Dict[str, int] = defaultdict(int)
    per_tier: Dict[str, int] = defaultdict(int)
    
    for r in risk_items_all:
        if r.verdict == "ALLOW":
            item = PoolExecutionPlanItemV1(
                intent_id=r.intent_id,
                symbol=r.symbol,
                timeframe=r.timeframe,
                bundle_id=r.bundle_id,
                action="PLACE_ORDER",
                side="BUY",
                order_type="MARKET",
                notional=r.proposed_notional,
                policy_exit=r.stop_type,
                notes=["dry_run"]
            )
            per_tf[r.timeframe] += 1
            per_tier[r.tier or "UNKNOWN"] += 1
        else:
            item = PoolExecutionPlanItemV1(
                intent_id=r.intent_id,
                symbol=r.symbol,
                timeframe=r.timeframe,
                bundle_id=r.bundle_id,
                action="SKIP_BLOCKED",
                side="BUY",
                order_type="MARKET",
                notional=0.0,
                policy_exit=r.stop_type,
                notes=["blocked", r.block_reason or "UNKNOWN"]
            )
        plan_items.append(item)
    
    exec_summary = PoolExecutionSummaryV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        selection_run_id=run_id,
        risk_run_id=run_id,
        planned_orders=len(allowed_items),
        skipped_orders=len(blocked_items),
        planned_total_notional=total_allowed,
        per_timeframe_counts=dict(per_tf),
        per_tier_counts=dict(per_tier),
        plan=plan_items,
        mode="DRY_RUN"
    )
    
    write_report_json(reports_dir / "pool_execution_summary_v1.json", exec_summary.to_dict())
    
    return {
        "status": "OK",
        "reports_dir": str(reports_dir),
        "allowed": len(allowed_items),
        "blocked": len(blocked_items),
        "allowed_count": len(allowed_items), # Legacy compat
        "blocked_count": len(blocked_items), # Legacy compat
        "mode": "DRY_RUN",
        "kill_switch": kill_switch_triggered
    }


def run_pool_phase2d_live_arm(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    arm_state: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Execute Pool Phase 2D: Write LIVE arm state report.
    
    Args:
        stage: Run stage (should be "live")
        run_id: Run ID
        trace_ctx: Context for determinism
        arm_state: Arm state configuration
        
    Returns:
        Summary dict
    """
    from tezaver.matrix.pool.live_arm_state_v1 import write_live_arm_state_report
    
    path = write_live_arm_state_report(stage, run_id, trace_ctx, arm_state)
    
    return {
        "status": "OK",
        "report_path": path,
        "armed": arm_state.get("armed", False)
    }


def run_pool_phase2d_restart_reconcile(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    before_provider,
    after_provider
) -> Dict[str, Any]:
    """
    Execute Pool Phase 2D: Restart reconcile report.
    
    Args:
        stage: Run stage
        run_id: Run ID
        trace_ctx: Context for determinism
        before_provider: OpenPositionsProviderV1 for before state
        after_provider: OpenPositionsProviderV1 for after state
        
    Returns:
        Summary dict
    """
    from tezaver.matrix.pool.pool_models_v1 import RestartReconcileReportV1
    from tezaver.matrix.pool.reconcile_engine_v1 import (
        reconcile_positions_on_restart,
        generate_reconcile_id
    )
    
    ev = trace_ctx.get("engine_version", "v1.0.0")
    df = trace_ctx.get("data_fingerprint", "UNKNOWN")
    cs = trace_ctx.get("config_signature", "UNKNOWN")
    reports_dir = resolve_reports_dir(stage, run_id)
    
    before_snap = before_provider.snapshot()
    after_snap = after_provider.snapshot()
    
    drift, verdict, suggested_actions = reconcile_positions_on_restart(before_snap, after_snap)
    
    reconcile_id = generate_reconcile_id(run_id, before_snap["count"], after_snap["count"])
    
    report = RestartReconcileReportV1(
        run_id=run_id,
        stage=stage,
        engine_version=ev,
        data_fingerprint=df,
        config_signature=cs,
        built_ts_iso=now_iso(),
        reconcile_id=reconcile_id,
        before={"open_positions_count": before_snap["count"], "positions": before_snap["positions"]},
        after={"open_positions_count": after_snap["count"], "positions": after_snap["positions"]},
        drift=drift,
        source={"provider": before_snap.get("source", "unknown"), "details": after_snap.get("source", "unknown")},
        verdict=verdict,
        suggested_actions=suggested_actions
    )
    
    path = reports_dir / "restart_reconcile_report_v1.json"
    write_report_json(path, report.to_dict())
    
    return {
        "status": "OK",
        "report_path": str(path),
        "verdict": verdict,
        "changed": drift["changed"]
    }


def run_pool_phase3b_replacement(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    open_positions: List[Dict[str, Any]],
    selected_items: List["PoolSelectionItemV1"],
    capacity: int,
    open_now: int,
    max_open_positions: int,
    reconcile_verdict: str,
    config: Optional[Dict[str, Any]] = None,
    kill_switch_triggered: bool = False,
    risk_limiter_triggered: bool = False
) -> Dict[str, Any]:
    """
    Execute Pool Phase 3B: Replacement evaluation (DRY-RUN).
    
    Args:
        stage: Run stage
        run_id: Run ID
        trace_ctx: Context for determinism
        open_positions: Current open positions list
        selected_items: Selected intents from Phase 2B
        capacity: Current capacity
        open_now: Number of open positions
        max_open_positions: Maximum position limit
        reconcile_verdict: Restart reconcile verdict
        config: Replacement config
        kill_switch_triggered: Kill switch state
        risk_limiter_triggered: Risk limiter state
        
    Returns:
        Summary dict
    """
    from tezaver.matrix.pool.replacement_engine_v1 import evaluate_replacement
    
    report = evaluate_replacement(
        run_id=run_id,
        stage=stage,
        trace_ctx=trace_ctx,
        open_positions=open_positions,
        selected_intents=selected_items,
        capacity=capacity,
        open_now=open_now,
        max_open_positions=max_open_positions,
        reconcile_verdict=reconcile_verdict,
        kill_switch_triggered=kill_switch_triggered,
        risk_limiter_triggered=risk_limiter_triggered,
        config=config
    )
    
    reports_dir = resolve_reports_dir(stage, run_id)
    path = reports_dir / "pool_replacement_report_v1.json"
    write_report_json(path, report.to_dict())
    
    return {
        "status": "OK",
        "report_path": str(path),
        "verdict": report.verdict,
        "skip_reason": report.skip_reason
    }


def run_pool_phase3c_replacement_plan(
    stage: str,
    run_id: str,
    trace_ctx: Dict[str, str],
    replacement_report: Dict[str, Any],
    reconcile_report: Dict[str, Any],
    bundle_registry = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Execute Pool Phase 3C: Build replacement plan.
    
    Args:
        stage: Run stage
        run_id: Run ID
        trace_ctx: Context for determinism
        replacement_report: Phase 3B replacement report
        reconcile_report: Phase 2D reconcile report
        bundle_registry: Bundle registry
        config: {"default_notional": float}
        
    Returns:
        Summary dict
    """
    from tezaver.matrix.pool.replacement_plan_engine_v1 import build_replacement_plan
    
    report = build_replacement_plan(
        run_id=run_id,
        stage=stage,
        trace_ctx=trace_ctx,
        replacement_report=replacement_report,
        reconcile_report=reconcile_report,
        bundle_registry=bundle_registry,
        config=config
    )
    
    reports_dir = resolve_reports_dir(stage, run_id)
    path = reports_dir / "pool_replacement_plan_v1.json"
    write_report_json(path, report.to_dict())
    
    return {
        "status": "OK",
        "report_path": str(path),
        "replacement_verdict": report.replacement_verdict,
        "has_plan": report.close_plan is not None,
        "skip_reason": report.skip_reason
    }
