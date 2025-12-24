from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class GameStageReason:
    stage: str  # PROSECUTOR, DEFENDER, JUDGE, JURY, LIMITS
    rule_code: str
    reason_code: str
    detail: str

@dataclass
class CourtDecisionTrace:
    verdict: str  # ALLOW, BLOCK, SKIP
    stage_reasons: List[GameStageReason] = field(default_factory=list)
    scorecard: Dict[str, Any] = field(default_factory=dict)
    limits: Dict[str, Any] = field(default_factory=dict)

@dataclass
class GameStep:
    ts: int  # ms
    bar_index: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    
    intent_summary: str  # "BUY @ 100" or "NONE"
    verdict: str
    court_trace: CourtDecisionTrace
    
    equity_after: float
    position_state: str  # "LONG (1.5)" or "FLAT"
    
    trade_ref_id: Optional[str] = None  # If a trade action occurred

@dataclass
class GameTrade:
    trade_id: str
    entry_ts: int
    entry_price: float
    exit_ts: Optional[int]
    exit_price: Optional[float]
    pnl_gross: float = 0.0
    fee: float = 0.0
    pnl_net: float = 0.0
    bars_held: int = 0
    ref_step_entry: int = 0
    ref_step_exit: Optional[int] = None
    status: str = "OPEN" # OPEN, CLOSED

@dataclass
class GameSummary:
    game_run_id: str
    bundle_id: str
    symbol: str
    timeframe: str
    
    final_equity: float
    return_pct: float
    max_drawdown: float
    trade_count: int
    win_rate: float
    profit_factor: float
    
    verdict_counts: Dict[str, int]
    top_block_reasons: List[Dict[str, Any]]
    
    created_ts: str = field(default_factory=lambda: datetime.utcnow().isoformat())
