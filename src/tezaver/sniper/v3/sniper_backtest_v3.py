"""
Sniper Backtest v3
==================

Clean, single-purpose backtest with strict invariants:
- used_count == selected_count (no filtering)
- trades == used_count (each row = 1 trade)
- pnl_signature_v2 guaranteed unique per trade set

Two modes:
- RAW: Use future_max_gain_pct directly
- TPSL: Apply TP/SL/HORIZON logic with capping
"""

from __future__ import annotations

import hashlib
from collections import Counter
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


def run_backtest_v3_from_trade_ids(
    df: pd.DataFrame,
    selected_trade_ids: List[str],
    risk: float = 0.01,
    mode: str = "experiment",  # "contract" | "experiment"
    max_risk: Optional[float] = None,
    tp_pct: float = 0.08,
    sl_pct: float = 0.03,
    max_bars: int = 20,
    pnl_mode: str = "TPSL",  # "RAW" | "TPSL"
) -> Dict[str, Any]:
    """
    Run backtest using ONLY specified trade_ids.
    
    NON-NEGOTIABLE INVARIANTS:
    - used_count == selected_count (RuntimeError if not)
    - trades == used_count (each row = 1 trade)
    
    Args:
        df: Full dataset DataFrame with trade_id column
        selected_trade_ids: List of trade_id strings to use
        risk: Risk per trade as decimal
        mode: "contract" (applies max_risk) or "experiment"
        max_risk: Maximum risk in contract mode
        tp_pct: Take profit percentage as decimal
        sl_pct: Stop loss percentage as decimal
        max_bars: Maximum bars to hold
        pnl_mode: "RAW" (use gain directly) or "TPSL" (apply capping)
        
    Returns:
        Dict with strict guarantees about used_count, trades, and signatures.
        
    Raises:
        RuntimeError: If invariants are violated.
    """
    if "trade_id" not in df.columns:
        raise ValueError("DataFrame must have 'trade_id' column")
    
    # Find gain column
    gain_col = None
    for c in ["future_max_gain_pct", "label_future_max_gain_pct", "gain_pct"]:
        if c in df.columns:
            gain_col = c
            break
    
    if gain_col is None:
        raise ValueError(f"No gain column found. Columns: {df.columns.tolist()}")
    
    # Subset by trade_ids - NO FILTERING, NO DEDUP
    sel = set(selected_trade_ids)
    selected_count = len(sel)
    
    df_used = df[df["trade_id"].isin(sel)].copy()
    used_count = len(df_used)
    
    # INVARIANT 1: used_count == selected_count
    if used_count != selected_count:
        found_ids = set(df_used["trade_id"].tolist())
        missing = list(sel - found_ids)[:10]
        raise RuntimeError(
            f"[V3_INVARIANT_VIOLATION] used={used_count} != selected={selected_count} "
            f"missing_sample={missing}"
        )
    
    # Sort by timestamp for consistent processing
    ts_col = None
    for c in ["event_time", "entry_ts", "ts"]:
        if c in df_used.columns:
            ts_col = c
            break
    if ts_col:
        df_used = df_used.sort_values(ts_col).reset_index(drop=True)
    
    # Apply risk limits in contract mode
    risk_eff = risk
    if mode == "contract" and max_risk is not None:
        risk_eff = min(risk, max_risk)
    
    # Run backtest: EACH ROW = 1 TRADE
    capital_start = 100.0
    equity = capital_start
    equity_history = [equity]
    wins = 0
    
    # Tracking
    exit_counts = {"TP": 0, "SL": 0, "HORIZON": 0, "RAW": 0}
    tp_capped = 0
    sl_capped = 0
    pnl_eff_list = []
    ledger = []
    
    for _, row in df_used.iterrows():
        trade_id = row["trade_id"]
        gain = row.get(gain_col, 0)
        equity_before = equity
        
        if pd.isna(gain):
            gain = 0.0
        
        # Normalize gain (percentage to decimal if needed)
        if abs(gain) > 1.0:
            gain_decimal = gain / 100.0
        else:
            gain_decimal = gain
        
        # Determine PnL based on mode
        if pnl_mode == "RAW":
            pnl_eff = gain_decimal
            exit_reason = "RAW"
        else:  # TPSL mode
            if gain_decimal >= tp_pct:
                pnl_eff = tp_pct
                exit_reason = "TP"
                tp_capped += 1
            elif gain_decimal <= -sl_pct:
                pnl_eff = -sl_pct
                exit_reason = "SL"
                sl_capped += 1
            else:
                pnl_eff = gain_decimal
                exit_reason = "HORIZON"
        
        pnl_eff_pct = pnl_eff * 100.0
        pnl_eff_list.append(pnl_eff_pct)
        exit_counts[exit_reason] += 1
        
        # Calculate PnL (compound: equity * risk * gain)
        pnl_amount = equity * risk_eff * pnl_eff
        equity = equity + pnl_amount
        equity_history.append(equity)
        
        if pnl_eff > 0:
            wins += 1
        
        ledger.append({
            "trade_id": trade_id,
            "pnl_raw_pct": round(gain_decimal * 100, 4),
            "pnl_eff_pct": round(pnl_eff_pct, 4),
            "pnl_amount": round(pnl_amount, 4),
            "exit_reason": exit_reason,
            "equity_before": round(equity_before, 2),
            "equity_after": round(equity, 2),
        })
    
    # INVARIANT 2: trades == used_count
    trades = len(ledger)
    if trades != used_count:
        raise RuntimeError(
            f"[V3_INVARIANT_VIOLATION] trades={trades} != used_count={used_count}"
        )
    
    # Calculate stats
    win_rate = (wins / trades * 100.0) if trades > 0 else 0.0
    pnl_pct = (equity / capital_start - 1.0) * 100.0
    
    # Max drawdown
    max_dd = 0.0
    peak = equity_history[0]
    for eq in equity_history:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (eq / peak - 1.0) * 100.0
            if dd < max_dd:
                max_dd = dd
    
    # Compute pnl_signature_v2 (trade_id + pnl + exit - guaranteed unique per trade set)
    sig_parts = []
    for t in ledger:
        sig_parts.append(f"{t['trade_id']}|{t['pnl_eff_pct']:.10f}|{t['exit_reason']}")
    sig_parts.sort()
    sig_str = f"{trades}|" + "|".join(sig_parts)
    pnl_signature_v2 = hashlib.sha1(sig_str.encode()).hexdigest()[:12]
    
    # Top PnL bins (histogram)
    pnl_rounded = [f"{p:.10f}" for p in pnl_eff_list]
    pnl_counter = Counter(pnl_rounded)
    top_pnl_bins = pnl_counter.most_common(10)
    pnl_unique_count = len(pnl_counter)
    
    # Percentile stats
    def calc_stats(arr):
        if not arr:
            return {"min": 0, "mean": 0, "p50": 0, "p90": 0, "max": 0}
        arr_np = np.array(arr)
        return {
            "min": round(float(np.min(arr_np)), 2),
            "mean": round(float(np.mean(arr_np)), 2),
            "p50": round(float(np.percentile(arr_np, 50)), 2),
            "p90": round(float(np.percentile(arr_np, 90)), 2),
            "max": round(float(np.max(arr_np)), 2),
        }
    
    return {
        # Core metrics
        "capital_start": capital_start,
        "capital_end": round(equity, 2),
        "pnl_pct": round(pnl_pct, 2),
        "win_rate": round(win_rate, 2),
        "max_drawdown_pct": round(max_dd, 2),
        
        # Invariant proofs (guaranteed: selected == used == trades)
        "selected_count": selected_count,
        "used_count": used_count,
        "trades": trades,
        
        # Signatures
        "pnl_signature_v2": pnl_signature_v2,
        
        # Exit distribution
        "exit_reason_counts": exit_counts,
        "tp_capped_count": tp_capped,
        "sl_capped_count": sl_capped,
        
        # Histogram
        "pnl_unique_count": pnl_unique_count,
        "top_pnl_bins": top_pnl_bins,
        "pnl_eff_stats": calc_stats(pnl_eff_list),
        
        # Mode info
        "pnl_mode": pnl_mode,
        "risk_effective": risk_eff,
        
        # Sample ledger
        "ledger_sample": ledger[:20],
    }
