# Matrix Live State Tools
"""
Utilities for reading live cell state from disk.

Provides summaries of equity, PnL, and trade history from state files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


STATE_DIR = Path("data/live_state")


@dataclass
class LiveCellStateSummary:
    """Summary of a live cell's state from disk."""
    symbol: str
    timeframe: str
    profile_id: str
    equity: Optional[float]
    pnl_pct: Optional[float]
    trade_count: int
    last_side: Optional[str]
    last_pnl: Optional[float]
    last_ts: Optional[str]
    state_file: Path


def _build_state_file_path(symbol: str, timeframe: str, profile_id: str) -> Path:
    """Build the path to a cell's state file."""
    filename = f"{symbol}_{timeframe}_{profile_id}.json"
    return STATE_DIR / filename


def load_live_cell_state(
    symbol: str,
    timeframe: str,
    profile_id: str,
    initial_capital: float,
) -> LiveCellStateSummary:
    """
    Load live cell state summary from disk.
    
    Args:
        symbol: Trading symbol (e.g. BTCUSDT)
        timeframe: Timeframe (e.g. 15m)
        profile_id: Profile identifier
        initial_capital: Initial capital for PnL calculation
    
    Returns:
        LiveCellStateSummary with current state or empty if no state file.
    """
    state_file = _build_state_file_path(symbol, timeframe, profile_id)
    
    # No state file exists
    if not state_file.exists():
        return LiveCellStateSummary(
            symbol=symbol,
            timeframe=timeframe,
            profile_id=profile_id,
            equity=None,
            pnl_pct=None,
            trade_count=0,
            last_side=None,
            last_pnl=None,
            last_ts=None,
            state_file=state_file,
        )

    # Try to load state file
    try:
        data: Dict[str, Any]
        with state_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # Corrupt file, return empty state
        return LiveCellStateSummary(
            symbol=symbol,
            timeframe=timeframe,
            profile_id=profile_id,
            equity=None,
            pnl_pct=None,
            trade_count=0,
            last_side=None,
            last_pnl=None,
            last_ts=None,
            state_file=state_file,
        )

    # Extract equity
    equity = float(data.get("equity", initial_capital))
    ledger: List[Dict[str, Any]] = list(data.get("ledger", []))

    # Calculate PnL %
    pnl_pct: Optional[float] = None
    if initial_capital > 0:
        pnl_pct = (equity / float(initial_capital) - 1.0) * 100.0

    # Extract last trade info
    trade_count = len(ledger)
    last_side: Optional[str] = None
    last_pnl: Optional[float] = None
    last_ts: Optional[str] = None
    
    if trade_count > 0:
        last = ledger[-1]
        last_side = str(last.get("side") or last.get("action") or "")
        last_pnl = float(last.get("pnl", 0.0)) if "pnl" in last else None
        # Try various timestamp keys
        ts_val = last.get("timestamp") or last.get("ts") or last.get("time")
        last_ts = str(ts_val) if ts_val is not None else None

    return LiveCellStateSummary(
        symbol=symbol,
        timeframe=timeframe,
        profile_id=profile_id,
        equity=equity,
        pnl_pct=pnl_pct,
        trade_count=trade_count,
        last_side=last_side,
        last_pnl=last_pnl,
        last_ts=last_ts,
        state_file=state_file,
    )


def load_all_live_states(
    profiles: List[Dict[str, Any]],
    initial_capital: float,
) -> List[LiveCellStateSummary]:
    """
    Load state summaries for a list of profiles.
    
    Args:
        profiles: List of dicts with symbol, timeframe, profile_id
        initial_capital: Initial capital for PnL calculation
    
    Returns:
        List of LiveCellStateSummary for each profile.
    """
    summaries = []
    for p in profiles:
        summary = load_live_cell_state(
            symbol=p["symbol"],
            timeframe=p["timeframe"],
            profile_id=p["profile_id"],
            initial_capital=initial_capital,
        )
        summaries.append(summary)
    return summaries
