"""
Sniper Benchmark Service
========================

Provides theoretical performance targets (Benchmarks) for bundles based on their metadata (Symbol, Timeframe, Tier).
Used by Sniper to determine if a bundle has reached its optimization potential.
"""
from typing import Dict, Any, Optional

# Default Theoretical Benchmarks (can be moved to config later)
# Format: Tier -> {target_pnl_pct, target_win_rate}
DEFAULT_BENCHMARKS = {
    "DIAMOND": {"target_pnl": 0.50, "target_wr": 0.70}, # 50% PnL, 70% WR
    "GOLD": {"target_pnl": 0.30, "target_wr": 0.60},    # 30% PnL, 60% WR
    "SILVER": {"target_pnl": 0.15, "target_wr": 0.55},  # 15% PnL, 55% WR
    "BRONZE": {"target_pnl": 0.05, "target_wr": 0.51},  # 5% PnL, 51% WR
    "UNKNOWN": {"target_pnl": 0.05, "target_wr": 0.50}
}

# Allow per-coin overrides if needed
COIN_MULTIPLIERS = {
    "ADAUSDT": 1.2, # ADA often has higher volatility/returns
    "BTCUSDT": 0.8  # BTC is more stable, lower PnL targets
}

class BenchmarkService:
    def get_benchmark(self, symbol: str, timeframe: str, tier: str) -> Dict[str, float]:
        """
        Returns the benchmark targets for a given bundle profile.
        
        Returns:
            {
                "target_pnl": float, # e.g. 0.30 for 30%
                "target_wr": float   # e.g. 0.60 for 60%
            }
        """
        base = DEFAULT_BENCHMARKS.get(tier, DEFAULT_BENCHMARKS["UNKNOWN"])
        multiplier = COIN_MULTIPLIERS.get(symbol, 1.0)
        
        # Adjust PnL by coin volatility/multiplier
        adjusted_pnl = base["target_pnl"] * multiplier
        
        return {
            "target_pnl": round(adjusted_pnl, 2),
            "target_wr": base["target_wr"]
        }

    def evaluate_sniper_performance(self, achieved_pnl: float, benchmark_pnl: float, tolerance: float = 0.10) -> bool:
        """
        Checks if achieved PnL is within tolerance of (or exceeds) the benchmark.
        Criteria: Achieved >= Benchmark * (1 - tolerance)
        """
        target = benchmark_pnl * (1.0 - tolerance)
        return achieved_pnl >= target
