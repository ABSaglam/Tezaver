# Matrix V2 Core Module
"""
Core module provides the foundational types, protocols, and engine for Matrix v2.
"""

from .types import MarketSignal, TradeDecision, ExecutionReport, MatrixEventLogEntry
from .account import Position, AccountState, AccountLedgerEntry, IAccountStore
from .engine import IAnalyzer, IStrategist, IExecutor, UnifiedEngine
from .guardrail import GuardrailConfig, GuardrailDecision, GuardrailController
from .profile import MatrixCellProfile, MatrixProfileRepository
from .datafeed import IDataFeed
from .clock import IClock

__all__ = [
    # Types
    "MarketSignal",
    "TradeDecision",
    "ExecutionReport",
    "MatrixEventLogEntry",
    # Account
    "Position",
    "AccountState",
    "AccountLedgerEntry",
    "IAccountStore",
    # Engine
    "IAnalyzer",
    "IStrategist",
    "IExecutor",
    "UnifiedEngine",
    # Guardrail
    "GuardrailConfig",
    "GuardrailDecision",
    "GuardrailController",
    # Profile
    "MatrixCellProfile",
    "MatrixProfileRepository",
    # DataFeed & Clock
    "IDataFeed",
    "IClock",
]
