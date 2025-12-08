from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime

class DataState(Enum):
    """
    State of the data for a specific coin.
    FRESH: Data is up-to-date.
    STALE: Data is outdated.
    MISSING: Data has not been fetched yet.
    """
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"

@dataclass
class CoinState:
    """
    Represents the holistic state of a coin in the Tezaver universe.
    """
    symbol: str
    data_state: DataState = DataState.MISSING
    last_update: Optional[datetime] = None
    last_price: float = 0.0  # Added for Market Summary
    indicators_ready: bool = False
    
    # Persona & Soul
    persona_summary: List[str] = field(default_factory=list)  # e.g., ["Tank", "LowPump"]
    trend_soul_score: int = 0  # 0-100: Represents the mood/soul of the trend, not just direction.
    
    # Harmony & Trust
    harmony_score: int = 0     # 0-100: How harmonious the price action is with indicators.
    betrayal_score: int = 0    # 0-100: Likelihood of a sudden reversal or trap.
    volume_trust: int = 0      # 0-100: "Volume reveals the sincerity of the move."
    
    # Risk & Opportunity
    risk_level: str = "medium" # "low" | "medium" | "high"
    pattern_status: str = "none" # "none" | "basic" | "trained"
    opportunity_score: int = 0 # 0-100: Overall attractiveness of the trade.
    
    # System Self-Reflection
    self_trust_score: int = 0  # 0-100: How confident the system is in its own analysis.
    
    # Market Regime & Shock Detection (M15)
    regime: str = "unknown"    # "range_bound" | "trending" | "chaotic" | "low_liquidity"
    shock_risk: int = 0        # 0-100: Risk of manipulation/shock events
    
    # Meta
    export_ready: bool = False # Ready for cloud export?
    notes: str = ""            # User notes
    custom_fields: Dict[str, Any] = field(default_factory=dict) # For future plugins
