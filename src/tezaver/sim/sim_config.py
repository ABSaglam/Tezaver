"""
Tezaver Sim v1 - Simulation Configuration
=========================================

Defines the configuration data structures for Rally Simulator.
"""

from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class RallySimConfig:
    """
    Configuration for a Rally Simulation run.
    """
    symbol: str
    timeframe: str  # "15m", "1h", "4h"
    
    # Entry Filters
    min_quality_score: float = 0.0
    allowed_shapes: List[str] = field(default_factory=lambda: ["clean", "choppy", "spike", "weak"])
    min_future_max_gain_pct: Optional[float] = None
    
    # Context Filters
    require_trend_soul_4h_gt: Optional[float] = None  # e.g. 60
    require_rsi_1d_gt: Optional[float] = None         # e.g. 50
    
    # Trade Management
    tp_pct: float = 0.05       # Take Profit (0.05 = 5%)
    sl_pct: float = 0.02       # Stop Loss (0.02 = 2%)
    risk_per_trade_pct: float = 0.01  # Risk 1% of equity per trade
    max_horizon_bars: int = 48 # Max bars to hold position (timeout)
    
    # Simulation Settings
    initial_equity: float = 10000.0
