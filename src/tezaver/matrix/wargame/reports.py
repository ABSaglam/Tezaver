# Matrix V2 Wargame Reports
"""
Report generation for wargame simulations.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class WargameReport:
    """
    Report summarizing wargame simulation results.
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
