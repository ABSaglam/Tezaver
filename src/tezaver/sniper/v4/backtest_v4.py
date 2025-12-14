"""
Sniper v4 - Backtest Module
============================

Override-only backtest with strict invariants:
- used_count == len(selected_trade_ids)
- trades == used_count (each row = 1 trade)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

import pandas as pd

from tezaver.sniper.v4.hashing_v4 import compute_pnl_signature


@dataclass
class BacktestResult:
    """Result of backtest execution."""
    capital_start: float
    capital_end: float
    pnl_pct: float
    win_rate: float
    trades: int
    used_count: int
    selected_count: int
    pnl_signature: str
    equity_curve: List[float]
    pnl_list: List[float]
    exit_counts: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "capital_start": self.capital_start,
            "capital_end": round(self.capital_end, 2),
            "pnl_pct": round(self.pnl_pct, 2),
            "win_rate": round(self.win_rate, 2),
            "trades": self.trades,
            "used_count": self.used_count,
            "selected_count": self.selected_count,
            "pnl_signature": self.pnl_signature,
            "exit_counts": self.exit_counts,
        }


def run_backtest_from_trade_ids(
    df: pd.DataFrame,
    selected_trade_ids: List[str],
    risk: float = 0.01,
    tp_pct: float = 0.08,
    sl_pct: float = 0.03,
    sizing_mode: str = "equity_pct",  # "equity_pct" | "initial_notional"
) -> BacktestResult:
    """
    Run backtest using ONLY specified trade_ids.
    
    NON-NEGOTIABLE INVARIANTS:
    - used_count == len(selected_trade_ids)
    - trades == used_count (each row = 1 trade)
    
    Args:
        df: Full dataset with trade_id column
        selected_trade_ids: List of trade_id strings to use
        risk: Risk per trade as decimal (e.g., 0.01 = 1%)
        tp_pct: Take profit as decimal (e.g., 0.08 = 8%)
        sl_pct: Stop loss as decimal (e.g., 0.03 = 3%)
        sizing_mode: "equity_pct" (compound) or "initial_notional" (fixed)
        
    Returns:
        BacktestResult with all metrics
        
    Raises:
        RuntimeError: If invariants are violated
    """
    if "trade_id" not in df.columns:
        raise ValueError("DataFrame must have 'trade_id' column")
    
    selected_count = len(selected_trade_ids)
    
    # Find gain/drawdown columns
    gain_col = None
    for c in ["future_max_gain_pct", "label_future_max_gain_pct", "gain_pct"]:
        if c in df.columns:
            gain_col = c
            break
    
    dd_col = None
    for c in ["future_min_drawdown_pct", "min_drawdown_pct"]:
        if c in df.columns:
            dd_col = c
            break
    
    if gain_col is None:
        raise ValueError(f"No gain column found. Columns: {df.columns.tolist()}")
    
    # Subset by trade_ids
    sel_set = set(selected_trade_ids)
    df_sel = df[df["trade_id"].isin(sel_set)].copy()
    used_count = len(df_sel)
    
    # INVARIANT 1: used_count == selected_count
    if used_count != selected_count:
        found_ids = set(df_sel["trade_id"].tolist())
        missing = list(sel_set - found_ids)[:5]
        raise RuntimeError(
            f"[V4_USED_MISMATCH] used={used_count} != selected={selected_count} "
            f"missing_sample={missing}"
        )
    
    # Sort by timestamp for consistent processing
    ts_col = None
    for c in ["event_time", "entry_ts", "ts"]:
        if c in df_sel.columns:
            ts_col = c
            break
    if ts_col:
        df_sel = df_sel.sort_values(ts_col).reset_index(drop=True)
    
    # Run backtest: EACH ROW = 1 TRADE
    capital_start = 100.0
    equity = capital_start
    equity_curve = [equity]
    wins = 0
    
    exit_counts = {"TP": 0, "SL": 0, "HORIZON": 0}
    pnl_list = []
    
    for _, row in df_sel.iterrows():
        gain = row.get(gain_col, 0)
        dd = row.get(dd_col, 0) if dd_col else 0
        
        if pd.isna(gain):
            gain = 0.0
        if pd.isna(dd):
            dd = 0.0
        
        # Normalize (handle both 0.08 and 8.0 formats)
        if abs(gain) > 1.0:
            gain = gain / 100.0
        if abs(dd) > 1.0:
            dd = dd / 100.0
        
        # TP/SL conservative logic:
        # - If drawdown hits SL first, take SL loss
        # - Elif gain reaches TP, take TP profit
        # - Else horizon (use actual gain)
        if dd <= -sl_pct:
            pnl = -sl_pct
            exit_reason = "SL"
        elif gain >= tp_pct:
            pnl = tp_pct
            exit_reason = "TP"
        else:
            pnl = gain
            exit_reason = "HORIZON"
        
        pnl_list.append(pnl)
        exit_counts[exit_reason] += 1
        
        # Equity update
        if sizing_mode == "initial_notional":
            equity += capital_start * risk * pnl
        else:  # equity_pct (compound)
            equity *= (1 + risk * pnl)
        
        equity_curve.append(equity)
        
        if pnl > 0:
            wins += 1
    
    trades = len(pnl_list)
    
    # INVARIANT 2: trades == used_count
    if trades != used_count:
        raise RuntimeError(
            f"[V4_TRADES_MISMATCH] trades={trades} != used_count={used_count}"
        )
    
    # Calculate stats
    win_rate = (wins / trades * 100.0) if trades > 0 else 0.0
    pnl_pct = (equity / capital_start - 1.0) * 100.0
    
    # Compute PnL signature
    pnl_signature = compute_pnl_signature(pnl_list)
    
    return BacktestResult(
        capital_start=capital_start,
        capital_end=equity,
        pnl_pct=pnl_pct,
        win_rate=win_rate,
        trades=trades,
        used_count=used_count,
        selected_count=selected_count,
        pnl_signature=pnl_signature,
        equity_curve=equity_curve,
        pnl_list=pnl_list,
        exit_counts=exit_counts,
    )
