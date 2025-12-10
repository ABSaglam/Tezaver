# Matrix V2 Account Module
"""
Account state and ledger management for Matrix v2.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, Literal


@dataclass
class Position:
    """
    Represents an open trading position.
    """
    position_id: str
    symbol: str
    side: Literal["long", "short"]
    entry_price: float
    quantity: float
    stop_loss: float | None = None
    take_profit: float | None = None
    entry_time: datetime = field(default_factory=datetime.now)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class AccountState:
    """
    Represents the current state of a trading account.
    """
    profile_id: str
    capital: float
    available_margin: float
    positions: list[Position] = field(default_factory=list)
    daily_pnl: float = 0.0
    total_pnl: float = 0.0
    trade_count: int = 0
    last_updated: datetime = field(default_factory=datetime.now)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class AccountLedgerEntry:
    """
    Represents a single entry in the account ledger for audit trail.
    """
    entry_id: str
    profile_id: str
    entry_type: Literal["deposit", "withdrawal", "trade_pnl", "commission", "adjustment"]
    amount: float
    balance_after: float
    timestamp: datetime = field(default_factory=datetime.now)
    reference_id: str | None = None  # e.g., execution_id for trade entries
    notes: str = ""


class IAccountStore(Protocol):
    """
    Protocol for account storage operations.
    
    Implementations can be live (persistent storage) or wargame (in-memory).
    """
    
    def load_account(self, profile_id: str) -> AccountState:
        """Load account state for a given profile."""
        ...
    
    def save_account(self, profile_id: str, state: AccountState) -> None:
        """Save account state for a given profile."""
        ...
    
    def append_ledger(self, profile_id: str, entry: AccountLedgerEntry) -> None:
        """Append a ledger entry for audit trail."""
        ...
