"""
Sniper Promotion Manager
========================

Analyzes Matrix Simulation (War) performance and manages bundle promotion/demotion.
Uses PortfolioStateV2 as the data source.
"""
import logging
from typing import Dict, Any, List
from tezaver.matrix.pool.portfolio_models_v2 import PortfolioStateV2, PortfolioPositionV2
from tezaver.matrix.sniper.certification_registry import (
    CertificationRegistry, 
    STAGE_CANDIDATE, 
    STAGE_SNIPER_PASSED, 
    STAGE_LIVE_CERTIFIED,
    STAGE_DEMOTED
)

logger = logging.getLogger(__name__)

# Default Thresholds
MIN_TRADES = 3
WIN_RATE_PROMOTION = 0.60
PNL_DEMOTION_LIMIT = -0.05  # -5%

from tezaver.matrix.sniper.benchmark_service import BenchmarkService

class PromotionManager:
    def __init__(self, cert_registry: CertificationRegistry = None, benchmark_service: BenchmarkService = None):
        self.cert_registry = cert_registry or CertificationRegistry()
        self.benchmark_service = benchmark_service or BenchmarkService()

    def update_promotions_from_portfolio(self, portfolio: PortfolioStateV2):
        """
        Processes a portfolio state (War Simulation) and updates certification status.
        Currently focuses on WAR -> LIVE promotion (Phase 2 -> Phase 3).
        
        Note: The SNIPER -> WAR promotion (Phase 1 -> Phase 2) is typically handled 
        by the automated backtest runner, but could be integrated here if we feed backtest results as pseudo-portfolio.
        """
        # 1. Aggregate performance by bundle_id
        bundle_stats = {} 
        
        for pos in portfolio.positions:
            if not pos.bundle_id:
                continue
                
            bid = pos.bundle_id
            if bid not in bundle_stats:
                bundle_stats[bid] = {"pnl": 0.0, "trades": 0, "wins": 0, "symbol": pos.symbol, "tf": pos.timeframe}
            
            if pos.status == "CLOSED":
                bundle_stats[bid]["pnl"] += pos.realized_pnl
                bundle_stats[bid]["trades"] += 1
                if pos.realized_pnl > 0:
                    bundle_stats[bid]["wins"] += 1
        
        # 2. Evaluate each bundle
        for bid, stats in bundle_stats.items():
            current_stage = self.cert_registry.get_bundle_stage(bid)
            trades = stats["trades"]
            
            if trades < MIN_TRADES:
                continue
            
            # Retrieve Benchmark
            # We assume tier is available (or we fetch from registry/manifest - strict lookup needed later)
            # For now defaulting to UNKNOWN if we can't easily get tier without loading manifest
            # In a real impl, we should load the bundle manifest to get the tier.
            # Let's assume a default UNKNOWN for safety in this loop or pass tier map.
            tier = "UNKNOWN" 
            
            bench = self.benchmark_service.get_benchmark(stats["symbol"], stats["tf"] or "1h", tier)
            
            win_rate = stats["wins"] / trades
            total_pnl = stats["pnl"]
            
            # --- WAR STAGE EVALUATION (Target: WinRate Benchmark) ---
            if current_stage == STAGE_SNIPER_PASSED:
                # In War, we want to see if it sustains the win rate
                target_wr = bench["target_wr"]
                # Allow a small tolerance for real world messiness (e.g. 10% less than target)
                passing_wr = target_wr * 0.90
                
                if win_rate >= passing_wr and total_pnl > 0:
                    reason = f"War Proven: WR={win_rate:.2f} (Target {target_wr:.2f}), PnL={total_pnl:.2f}"
                    
                    metrics = {
                        "actual_wr": round(win_rate, 2),
                        "target_wr": target_wr,
                        "actual_pnl": round(total_pnl, 2),
                        "target_pnl": bench["target_pnl"], # Keeping PnL target context even if WR was the trigger
                        "total_trades": trades
                    }
                    self.cert_registry.certify_live_ready(bid, reason=reason, metrics=metrics)
            
            # --- LIVE STAGE EVALUATION (Demotion) ---
            elif current_stage == STAGE_LIVE_CERTIFIED:
                # Demote if significant degradation
                if total_pnl < PNL_DEMOTION_LIMIT or win_rate < 0.40:
                     reason = f"Demoted: WR={win_rate:.0%}, PnL={total_pnl:.2f}"
                     self.cert_registry.demote_bundle(bid, reason=reason)

    def evaluate_sniper_backtest(self, bundle_id: str, symbol: str, timeframe: str, tier: str, backtest_pnl_pct: float) -> bool:
        """
        Evaluates a Sniper Backtest result against the PnL Benchmark.
        If passed, promotes to SNIPER_PASSED (War Ready).
        """
        bench = self.benchmark_service.get_benchmark(symbol, timeframe, tier)
        target_pnl = bench["target_pnl"]
        
        # Check PnL (Target-Driven Optimization)
        # We allow a 10% tolerance by default in BenchmarkService, but here we enforce the logic
        is_passed = self.benchmark_service.evaluate_sniper_performance(backtest_pnl_pct, target_pnl)
        
        if is_passed:
            reason = f"Sniper Vizesi: PnL={backtest_pnl_pct:.2f} (Target {target_pnl:.2f})"
            
            metrics = {
                "actual_pnl": round(backtest_pnl_pct, 2),
                "target_pnl": target_pnl,
                "bench_tier": tier,
                "delta": round(backtest_pnl_pct - target_pnl, 2)
            }
            self.cert_registry.certify_sniper_pass(bundle_id, reason=reason, metrics=metrics)
            return True
            
        return False

    def process_run(self, stage: str, run_id: str):
        """Helper to process a specific Matrix run."""
        from tezaver.matrix.pool.portfolio_state_store_sim_v1 import load_state_v2
        try:
            state = load_state_v2(stage, run_id)
            if state:
                self.update_promotions_from_portfolio(state)
        except Exception as e:
            logger.error(f"Failed to process run {run_id} for promotion: {e}")
