# Matrix V2 Wargame Reports
"""
Report generation for wargame simulations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class WargameReport:
    """
    Report summarizing wargame simulation results.
    
    Extended with profile status and risk contract info for v2.
    """
    scenario_id: str
    profile_id: str
    capital_start: float
    capital_end: float
    trade_count: int
    win_rate: float
    max_drawdown: float = 0.0
    # New fields for equity tracking
    equity_curve: List[float] = field(default_factory=list)
    max_drawdown_pct: float = 0.0
    events: List[Dict[str, Any]] = field(default_factory=list)
    # V2 fields: profile awareness
    profile_status: Optional[str] = None  # APPROVED / EXPERIMENTAL / DISABLED
    risk_contract_max: Optional[float] = None  # max_risk_per_trade from contract



def compute_max_drawdown_pct(equity_curve: list[float]) -> float:
    """
    Compute maximum drawdown from equity curve.
    
    Tracks peak equity and calculates the largest drop as percentage.
    
    Args:
        equity_curve: List of equity values over time.
        
    Returns:
        Max drawdown as negative percentage (e.g., -0.15 = -15%).
    """
    if not equity_curve:
        return 0.0
    
    peak = equity_curve[0]
    max_dd = 0.0
    
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = eq / peak - 1.0  # Negative when below peak
        if dd < max_dd:
            max_dd = dd
    
    return max_dd


def build_dummy_report(scenario_id: str, profile_id: str) -> WargameReport:
    """
    Build a dummy report for testing.
    
    Args:
        scenario_id: Scenario identifier.
        profile_id: Profile identifier.
        
    Returns:
        WargameReport with placeholder values.
    """
    return WargameReport(
        scenario_id=scenario_id,
        profile_id=profile_id,
        capital_start=1000.0,
        capital_end=1050.0,
        trade_count=10,
        win_rate=0.6,
        max_drawdown=0.05,
        equity_curve=[1000.0, 1020.0, 1010.0, 1050.0],
        max_drawdown_pct=-0.0098,
    )


# =============================================================================
# Hybrid War Game Result
# =============================================================================

@dataclass
class HybridWargameResult:
    """
    Result combining Pattern and Full Replay war game runs.
    
    Allows side-by-side comparison of the two data sources.
    """
    symbol: str
    timeframe: str
    profile_id: str
    risk: float
    mode: str  # "contract" / "experiment"
    tightness: int

    pattern_report: WargameReport
    full_replay_report: WargameReport

    @property
    def delta_capital(self) -> float:
        """Difference in final capital (full_replay - pattern)."""
        return self.full_replay_report.capital_end - self.pattern_report.capital_end

    @property
    def delta_pnl_pct(self) -> float:
        """Difference in PnL percentage."""
        pr_pnl = (self.pattern_report.capital_end / self.pattern_report.capital_start - 1.0) * 100.0
        fr_pnl = (self.full_replay_report.capital_end / self.full_replay_report.capital_start - 1.0) * 100.0
        return fr_pnl - pr_pnl

    @property
    def delta_trades(self) -> int:
        """Difference in trade count."""
        return self.full_replay_report.trade_count - self.pattern_report.trade_count

    @property
    def delta_max_dd_pct(self) -> float:
        """Difference in max drawdown percentage."""
        return self.full_replay_report.max_drawdown_pct - self.pattern_report.max_drawdown_pct

