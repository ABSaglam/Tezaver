# Matrix V2 Live Account Store
"""
Live account storage implementation with JSON file persistence.

Supports saving/loading state from disk for LIVE trading durability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

from tezaver.matrix.core.account import IAccountStore, AccountState, AccountLedgerEntry
from tezaver.matrix.wargame.wargame_account_store import WargameAccountStore


@dataclass
class LiveAccountStore(IAccountStore):
    """
    Live/paper ortamında hesap durumunu yöneten sınıf.
    
    JSON dosyasına kaydederek restart sonrası state'i korur.
    """
    initial_capital: float = 1000.0
    state_file_path: Optional[str] = None
    
    _delegate: WargameAccountStore = field(init=False, repr=False)
    _state_path: Optional[Path] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._delegate = WargameAccountStore(initial_capital=self.initial_capital)
        self._state_path = Path(self.state_file_path) if self.state_file_path else None
        
        # Load existing state from disk if available
        if self._state_path is not None:
            self._load_state_from_disk()

    def _load_state_from_disk(self) -> None:
        """Load equity and ledger from state file."""
        if self._state_path is None or not self._state_path.exists():
            return
        try:
            with self._state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # Restore equity
            saved_equity = float(data.get("equity", self.initial_capital))
            self._delegate._equity = saved_equity
            # Restore ledger
            self._delegate._ledger = list(data.get("ledger", []))
            # Restore equity history
            self._delegate._equity_history = list(data.get("equity_history", [saved_equity]))
        except Exception:
            # Corrupt file, start fresh
            pass

    def _save_state_to_disk(self) -> None:
        """Save current equity and ledger to state file."""
        if self._state_path is None:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "equity": self._delegate.get_equity(),
            "ledger": self._delegate.get_ledger(),
            "equity_history": self._delegate.get_equity_history(),
        }
        with self._state_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_account(self, profile_id: str) -> AccountState:
        """Load account state for a profile."""
        return self._delegate.load_account(profile_id)

    def save_account(self, profile_id: str, state: AccountState) -> None:
        """Save account state."""
        self._delegate.save_account(profile_id, state)
        self._save_state_to_disk()

    def append_ledger(self, profile_id: str, entry: AccountLedgerEntry) -> None:
        """Append ledger entry."""
        self._delegate.append_ledger(profile_id, entry)
        self._save_state_to_disk()

    def apply_execution(self, execution: dict) -> None:
        """Apply execution to account, updating equity."""
        self._delegate.apply_execution(execution)
        self._save_state_to_disk()

    def get_equity(self) -> float:
        """Get current equity."""
        return self._delegate.get_equity()

    def get_equity_history(self) -> List[float]:
        """Get equity history for drawdown calculation."""
        return self._delegate.get_equity_history()

    def get_ledger(self) -> List[dict]:
        """Get trade ledger."""
        return self._delegate.get_ledger()

    def reset(self) -> None:
        """Reset all accounts, ledgers, and delete state file."""
        self._delegate.reset()
        if self._state_path is not None and self._state_path.exists():
            try:
                self._state_path.unlink()
            except Exception:
                pass
