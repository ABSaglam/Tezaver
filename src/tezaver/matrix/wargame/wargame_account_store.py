# Matrix V2 Wargame Account Store
"""
In-memory account storage for wargame simulations.
"""

from ..core.account import IAccountStore, AccountState, AccountLedgerEntry


class WargameAccountStore(IAccountStore):
    """
    In-memory account storage for wargame simulations.
    
    Stores account state and ledger entries in memory.
    Tracks equity and trade history for PnL calculation.
    """
    
    def __init__(self, initial_capital: float = 100.0) -> None:
        """
        Initialize wargame account store.
        
        Args:
            initial_capital: Starting capital for new accounts.
        """
        self._initial_capital = float(initial_capital)
        self._equity = float(initial_capital)
        self._accounts: dict[str, AccountState] = {}
        self._ledgers: dict[str, list[AccountLedgerEntry]] = {}
        self._trade_ledger: list[dict] = []
        self._equity_history: list[float] = [self._equity]  # Track equity over time
    
    def get_equity(self) -> float:
        """Get current equity."""
        return self._equity
    
    def get_ledger(self) -> list[dict]:
        """Get trade ledger (execution history)."""
        return list(self._trade_ledger)
    
    def get_equity_history(self) -> list[float]:
        """Get equity history for drawdown calculation."""
        return list(self._equity_history)
    
    def apply_execution(self, execution: dict) -> None:
        """
        Apply an execution to the account, updating equity.
        
        Args:
            execution: Dict containing pnl and event details.
        """
        pnl = float(execution.get("pnl", 0.0))
        self._equity += pnl
        self._trade_ledger.append(execution)
        self._equity_history.append(self._equity)  # Track equity after each trade
    
    def load_account(self, profile_id: str) -> AccountState:
        """
        Load or create account state for a profile.
        
        Args:
            profile_id: Unique profile identifier.
            
        Returns:
            AccountState for the profile.
        """
        if profile_id not in self._accounts:
            self._accounts[profile_id] = AccountState(
                profile_id=profile_id,
                capital=self._equity,
                available_margin=self._equity,
                positions=[],
                daily_pnl=0.0,
                total_pnl=self._equity - self._initial_capital,
                trade_count=len(self._trade_ledger),
            )
        else:
            # Update with current equity
            self._accounts[profile_id].capital = self._equity
            self._accounts[profile_id].available_margin = self._equity
            self._accounts[profile_id].total_pnl = self._equity - self._initial_capital
            self._accounts[profile_id].trade_count = len(self._trade_ledger)
        return self._accounts[profile_id]
    
    def save_account(self, profile_id: str, state: AccountState) -> None:
        """
        Save account state to memory.
        
        Args:
            profile_id: Unique profile identifier.
            state: Account state to save.
        """
        self._accounts[profile_id] = state
        self._equity = state.capital
    
    def append_ledger(self, profile_id: str, entry: AccountLedgerEntry) -> None:
        """
        Append ledger entry to memory.
        
        Args:
            profile_id: Unique profile identifier.
            entry: Ledger entry to append.
        """
        if profile_id not in self._ledgers:
            self._ledgers[profile_id] = []
        self._ledgers[profile_id].append(entry)
    
    def reset(self) -> None:
        """Reset all accounts and ledgers."""
        self._equity = self._initial_capital
        self._accounts.clear()
        self._ledgers.clear()
        self._trade_ledger.clear()
        self._equity_history = [self._equity]  # Reset history with initial capital
