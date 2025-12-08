"""
Tezaver Unified Engine Interfaces (M25)
=======================================

This module defines the abstract base classes for the Unified Engine architecture.
It enforces the separation of concerns between:
1. Analyzer: Detects market signals (Scout)
2. Strategist: Manages risk and decisions (Coach)
3. Executor: Handles order placement (Player)
"""

"""
Tezaver Matrix M25 Core Interfaces (The Trinity)
================================================

This module defines the core data structures and contracts for the Matrix Engine.
It follows the "Trinity Doctrine": Separation of Scouting, Coaching, and Execution.
"""

from typing import List, Dict, Any, Optional, Protocol, TypedDict, Literal
from datetime import datetime

# --- 1. Data Structures (The Language) ---

class MarketSignal(TypedDict):
    """
    Output of IAnalyzer (The Scout).
    Represents a raw observation from the market.
    """
    symbol: str
    timeframe: str
    signal_type: str  # e.g. "RALLY_START", "MONITOR"
    score: float      # 0.0 - 100.0 Confidence
    timestamp: datetime
    metadata: Dict[str, Any] # Extra data (current_price etc.)

class Position(TypedDict):
    """Represents a held position."""
    symbol: str
    qty: float
    avg_price: float
    unrealized_pnl: float

class AccountState(TypedDict):
    """
    State of the Wallet/Portfolio.
    Passed from Executor to Strategist.
    """
    equity: float               # Total Value (USDT)
    available_cash: float       # Free USDT
    positions: Dict[str, Position]

class TradeDecision(TypedDict):
    """
    Output of IStrategist (The Coach).
    Represents a tactical command.
    """
    action: Literal["NONE", "BUY", "SELL"]
    symbol: str
    quantity: float
    price: Optional[float]      # Limit price or None for Market
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: str

class ExecutionReport(TypedDict):
    """
    Output of IExecutor (The Player).
    Represents the result of an action.
    """
    success: bool
    status: Literal["FILLED", "REJECTED", "SKIPPED", "FAILED"]
    order_id: str
    symbol: str
    action: str
    filled_qty: float
    filled_price: float
    commission: float
    timestamp: datetime
    error_message: Optional[str]


# --- 2. Protocols (The Roles) ---

class IAnalyzer(Protocol):
    """
    The Scout.
    Responsible for analyzing market data and generating signals.
    """
    def analyze(self, symbol: str, timeframe: str, data: Any) -> List[MarketSignal]:
        ...

class IStrategist(Protocol):
    """
    The Coach.
    Responsible for making trade decisions based on signals and risk management.
    """
    def evaluate(self, signal: MarketSignal, account_state: AccountState) -> Optional[TradeDecision]:
        ...

class IExecutor(Protocol):
    """
    The Player.
    Responsible for executing trade decisions against a venue (Real or Sim).
    """
    def execute(self, decision: TradeDecision) -> ExecutionReport:
        ...
    
    def get_balance(self) -> AccountState:
        """Return current standardized account state."""
        ...
