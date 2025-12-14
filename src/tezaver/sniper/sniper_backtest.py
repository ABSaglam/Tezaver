"""
Sniper Backtest v1
==================

Simple backtest for sniper entries quality measurement.
Uses sniper_entries_v1.parquet + sniper_strategy_card_v1.json

Output: 100 → X capital, trade count, win rate, max drawdown.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional

import json
import hashlib
import pandas as pd
import numpy as np

from tezaver.sniper.sniper_ids import ensure_trade_id_column


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class SniperBacktestResult:
    """Result of sniper backtest."""
    symbol: str
    timeframe: str
    risk_per_trade: float
    capital_start: float
    capital_end: float
    pnl_pct: float
    trade_count: int
    win_rate: float
    max_drawdown_pct: float
    selected_entries: int
    total_entries: int
    entries_hash: str = ""
    trade_list: List[Dict[str, Any]] = None
    trade_ids_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Handle None for trade_list
        if d.get("trade_list") is None:
            d["trade_list"] = []
        return d


# =============================================================================
# Path Helpers
# =============================================================================

def _get_sniper_entries_path(symbol: str, timeframe: str) -> Path:
    """Get path to sniper entries dataset."""
    return Path("data/ai_datasets") / symbol.upper() / timeframe / "sniper_entries_v1.parquet"


def _get_sniper_card_path(symbol: str, timeframe: str) -> Path:
    """Get path to sniper strategy card."""
    return Path("data/coin_profiles") / symbol.upper() / timeframe / "sniper_strategy_card_v1.json"


def load_sniper_strategy_card(symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
    """Load sniper strategy card from JSON."""
    path = _get_sniper_card_path(symbol, timeframe)
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


# =============================================================================
# Entry Filter Application
# =============================================================================

def apply_entry_filters(df: pd.DataFrame, card: Dict[str, Any]) -> pd.DataFrame:
    """
    Apply entry filters from strategy card to DataFrame.
    
    Returns filtered DataFrame where all filter conditions are met.
    """
    if df.empty:
        return df
    
    entry_filters = card.get("entry_filters", {})
    if not entry_filters:
        return df
    
    mask = pd.Series([True] * len(df), index=df.index)
    
    for col_name, filt in entry_filters.items():
        if col_name not in df.columns:
            continue
        
        min_val = filt.get("min")
        max_val = filt.get("max")
        
        col_mask = df[col_name].notna()
        
        if min_val is not None:
            col_mask = col_mask & (df[col_name] >= min_val)
        if max_val is not None:
            col_mask = col_mask & (df[col_name] <= max_val)
        
        mask = mask & col_mask
    
    return df[mask].copy()



# =============================================================================
# Max Drawdown Calculation
# =============================================================================

def compute_max_drawdown_pct(equity_history: List[float]) -> float:
    """
    Compute maximum drawdown percentage from equity history.
    
    Returns:
        Max drawdown as negative percentage (e.g., -15.5 for -15.5% dd).
    """
    if len(equity_history) < 2:
        return 0.0
    
    peak = equity_history[0]
    max_dd = 0.0
    
    for eq in equity_history:
        if eq > peak:
            peak = eq
        if peak > 0:
            dd = (eq / peak - 1.0) * 100.0
            if dd < max_dd:
                max_dd = dd
    
    return max_dd


# =============================================================================
# Override-Only Backtest (Arena Mode)
# =============================================================================

def run_sniper_backtest_from_trade_ids(
    symbol: str,
    timeframe: str,
    selected_trade_ids: List[str],
    risk: float = 0.01,
    tp_pct: float = 0.08,
    sl_pct: float = 0.03,
    max_horizon_bars: int = 20,
    position_sizing_mode: str = "equity_pct",  # "initial_notional" | "equity_pct"
    disable_tp_sl_caps: bool = False,  # If True, use uncapped gains
    use_raw_pnl: bool = False,  # If True, use raw gain directly (no TP/SL/HORIZON logic)
) -> Dict[str, Any]:
    """
    Run backtest using ONLY specified trade_ids.
    
    NO card/profile loading.
    NO apply_entry_filters.
    NO dedup or single-position logic.
    Each row = 1 trade.
    
    HARD TRIPWIRE: If selected count != used count, raises RuntimeError.
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe string
        selected_trade_ids: List of trade_id strings to use
        risk: Risk per trade as decimal
        tp_pct: Take profit percentage as decimal (e.g., 0.08 = 8%)
        sl_pct: Stop loss percentage as decimal (e.g., 0.03 = 3%)
        max_horizon_bars: Maximum bars to hold
        position_sizing_mode: "initial_notional" (fixed) or "equity_pct" (compound)
        
    Returns:
        Dict with used_count, trades, capital_end, ledger, fingerprint, diagnostics.
    """
    symbol = symbol.upper()
    
    # Load dataset
    dataset_path = _get_sniper_entries_path(symbol, timeframe)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Sniper entries dataset not found: {dataset_path}")
    
    df = pd.read_parquet(dataset_path)
    df = ensure_trade_id_column(df)
    
    # Get gain column
    gain_col = None
    for c in ["future_max_gain_pct", "label_future_max_gain_pct", "gain_pct"]:
        if c in df.columns:
            gain_col = c
            break
    
    if gain_col is None:
        raise ValueError(f"No gain column found. Columns: {df.columns.tolist()}")
    
    # Subset by trade_ids - NO DEDUP, NO FILTERING
    sel = set(selected_trade_ids)
    df_used = df[df["trade_id"].isin(sel)].copy()
    
    # HARD TRIPWIRE: counts must match
    if len(df_used) != len(sel):
        found_ids = set(df_used["trade_id"].tolist())
        missing = list(sel - found_ids)[:20]
        raise RuntimeError(
            f"[ARENA_OVERRIDE_MISMATCH] selected={len(sel)} used={len(df_used)} "
            f"missing_sample={missing}"
        )
    
    # Sort by timestamp
    ts_col = None
    for c in ["event_time", "entry_ts", "ts"]:
        if c in df_used.columns:
            ts_col = c
            break
    if ts_col:
        df_used = df_used.sort_values(ts_col).reset_index(drop=True)
    
    # Run backtest: each row = 1 trade
    capital_start = 100.0
    equity = capital_start
    equity_history = [equity]
    wins = 0
    
    # Diagnostics tracking
    exit_counts = {"TP": 0, "SL": 0, "HORIZON": 0}
    tp_capped = 0
    sl_capped = 0
    pnl_raw_list = []
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
        
        pnl_raw = gain_decimal  # Raw PnL before capping
        pnl_raw_list.append(pnl_raw * 100)  # Store as percentage
        
        # Determine exit reason and effective PnL based on mode
        if use_raw_pnl:
            # RAW mode: use gain directly, no TP/SL/HORIZON logic
            pnl_eff = gain_decimal
            exit_reason = "RAW"
        elif disable_tp_sl_caps:
            # Caps disabled: keep TP/SL labels but don't cap the value
            if gain_decimal >= tp_pct:
                exit_reason = "TP"
                pnl_eff = gain_decimal  # uncapped
            elif gain_decimal <= -sl_pct:
                exit_reason = "SL"
                pnl_eff = gain_decimal  # uncapped
            else:
                pnl_eff = gain_decimal
                exit_reason = "HORIZON"
        else:
            # Normal mode: cap at TP/SL
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
        
        pnl_eff_list.append(pnl_eff * 100)  # Store as percentage
        exit_counts[exit_reason] += 1
        
        # Calculate PnL based on position sizing mode
        if position_sizing_mode == "initial_notional":
            risk_amount = capital_start * risk
        else:  # equity_pct (compound)
            risk_amount = equity * risk
        
        pnl_amount = risk_amount * pnl_eff / risk  # Scale to actual gain
        equity = equity + pnl_amount
        equity_history.append(equity)
        
        if pnl_eff > 0:
            wins += 1
        
        ledger.append({
            "trade_id": trade_id,
            "pnl_raw_pct": round(pnl_raw * 100, 4),
            "pnl_eff_pct": round(pnl_eff * 100, 4),
            "pnl_amount": round(pnl_amount, 4),
            "exit_reason": exit_reason,
            "equity_before": round(equity_before, 2),
            "equity_after": round(equity, 2),
        })
    
    # Calculate stats
    trade_count = len(ledger)
    win_rate = (wins / trade_count * 100.0) if trade_count > 0 else 0.0
    max_dd = compute_max_drawdown_pct(equity_history)
    pnl_pct = (equity / capital_start - 1.0) * 100.0
    
    # Compute fingerprint
    sorted_ids = sorted(sel)
    fingerprint = hashlib.sha1("|".join(sorted_ids).encode()).hexdigest()[:10]
    
    # Compute PnL signature v1 (based on effective PnL values, sorted)
    sorted_pnl_eff = sorted([round(p, 2) for p in pnl_eff_list])
    pnl_sig_str = "|".join([f"{p:.2f}" for p in sorted_pnl_eff])
    pnl_signature_v1 = hashlib.sha1(pnl_sig_str.encode()).hexdigest()[:10]
    
    # Compute PnL signature v2 (trade_id + pnl + exit_reason - guaranteed unique per trade set)
    sig_v2_parts = []
    for t in ledger:
        sig_v2_parts.append(f"{t['trade_id']}|{t['pnl_eff_pct']:.10f}|{t['exit_reason']}")
    sig_v2_parts.sort()
    pnl_sig_v2_str = f"{trade_count}|" + "|".join(sig_v2_parts)
    pnl_signature_v2 = hashlib.sha1(pnl_sig_v2_str.encode()).hexdigest()[:10]
    
    # Compute PnL histogram
    from collections import Counter
    pnl_eff_rounded = [round(p, 4) for p in pnl_eff_list]
    pnl_counter = Counter(pnl_eff_rounded)
    pnl_eff_unique_count = len(pnl_counter)
    pnl_eff_top_bins = pnl_counter.most_common(10)  # Top 10 most frequent values
    
    # Calculate percentile stats
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
        "used_count": len(df_used),
        "trades": trade_count,
        "capital_start": capital_start,
        "capital_end": round(equity, 2),
        "pnl_pct": round(pnl_pct, 2),
        "win_rate": round(win_rate, 2),
        "max_drawdown_pct": round(max_dd, 2),
        "used_trade_ids_sample": df_used["trade_id"].head(20).tolist(),
        "trade_fingerprint": fingerprint,
        "pnl_signature": pnl_signature_v1,  # Keep v1 for compatibility
        "pnl_signature_v2": pnl_signature_v2,  # New guaranteed-unique signature
        "position_sizing_mode": position_sizing_mode,
        "disable_tp_sl_caps": disable_tp_sl_caps,
        "use_raw_pnl": use_raw_pnl,
        "ledger": ledger[:20],  # First 20 for sample
        # Diagnostics
        "exit_reason_counts": exit_counts,
        "tp_capped_count": tp_capped,
        "sl_capped_count": sl_capped,
        "pnl_raw_stats": calc_stats(pnl_raw_list),
        "pnl_eff_stats": calc_stats(pnl_eff_list),
        "pnl_eff_unique_count": pnl_eff_unique_count,
        "pnl_eff_top_bins": pnl_eff_top_bins,
    }


# =============================================================================
# Main Backtest Function
# =============================================================================

def run_sniper_backtest_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
    risk_per_trade: float = 1.0,
    entries_override: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Run sniper backtest on sniper entries dataset.
    
    Args:
        symbol: Trading symbol.
        timeframe: Timeframe.
        risk_per_trade: Risk per trade (1.0 = full equity per trade).
        entries_override: Optional override for entries dataframe.
        
    Returns:
        Dictionary with backtest results.
    """
    symbol = symbol.upper()
    
    if entries_override is not None:
        df = entries_override.copy()
    else:
        # Load dataset
        dataset_path = _get_sniper_entries_path(symbol, timeframe)
        if not dataset_path.exists():
            raise FileNotFoundError(
                f"Sniper entries dataset not found: {dataset_path}. "
                f"Please ingest data first."
            )
        
        df = pd.read_parquet(dataset_path)
        
    # DEBUG: Compute Hash
    entries_hash = "EMPTY"
    if not df.empty:
        items = []
        # Support both 'event_id' and 'ts' variations
        for _, row in df.iterrows():
            eid = str(row.get("event_id", ""))
            ts = str(row.get("event_time", row.get("ts", "")))[:19]
            items.append(f"{eid}|{ts}")
        items.sort()
        entries_hash = hashlib.sha1("".join(items).encode()).hexdigest()[:10]
        
    print(f"[DEBUG BACKTEST] Symbol: {symbol}, Entries: {len(df)}, Hash: {entries_hash}")
    
    total_entries = len(df)
    
    if total_entries == 0:
        raise ValueError(f"Sniper entries dataset is empty for {symbol} {timeframe}")
    
    # Check for gain column
    gain_col = None
    for c in ["future_max_gain_pct", "label_future_max_gain_pct", "gain_pct"]:
        if c in df.columns:
            gain_col = c
            break
    
    if gain_col is None:
        raise ValueError(
            f"No gain column found in sniper entries. "
            f"Expected: future_max_gain_pct. Found: {df.columns.tolist()}"
        )
    
    # When entries_override is provided, skip card filtering (already filtered by arena runner)
    if entries_override is not None:
        # Ensure trade_id column exists for proper tracking
        df_filtered = ensure_trade_id_column(df.copy())
        selected_entries = len(df_filtered)
        
        # Log for debugging
        print(f"[BACKTEST] entries_override provided: {selected_entries} entries")
        
        card = {}  # No additional card filtering
        gain_threshold_pct = None  # Use actual gains without capping
    else:
        # Load strategy card and apply filters (original behavior)
        card = load_sniper_strategy_card(symbol, timeframe)
        if card is None:
            card = {"entry_filters": {}, "labels": {}}
        
        # Apply filters
        df_filtered = apply_entry_filters(df, card)
        selected_entries = len(df_filtered)
        
        # Get gain threshold from card
        labels = card.get("labels", {})
        gain_threshold_pct = labels.get("gain_threshold_pct")
    
    # Initialize equity tracking
    capital_start = 100.0
    equity = capital_start
    equity_history = [equity]
    wins = 0
    trades = 0
    
    # Sort by entry timestamp if available
    ts_col = None
    for c in ["entry_ts", "timestamp", "ts"]:
        if c in df_filtered.columns:
            ts_col = c
            break
    
    if ts_col:
        df_filtered = df_filtered.sort_values(ts_col).reset_index(drop=True)
    
    # Process each trade and collect trade list
    trade_list = []
    
    for idx, row in df_filtered.iterrows():
        gain = row[gain_col]
        
        if pd.isna(gain):
            continue
        
        # Get entry identifiers
        event_id = str(row.get("event_id", idx))
        entry_ts = row.get("event_time", row.get("ts", ""))
        if hasattr(entry_ts, "isoformat"):
            entry_ts_str = entry_ts.isoformat()[:19]
        else:
            entry_ts_str = str(entry_ts)[:19]
        
        trade_id = f"{event_id}|{entry_ts_str}"
        
        # Cap gain at threshold if set
        if gain_threshold_pct is not None and gain > gain_threshold_pct:
            gain = gain_threshold_pct
        
        # Calculate trade return (gain is already in decimal form, e.g., 0.08 = 8%)
        # Note: If gain is in percentage (8.0), normalize
        if abs(gain) > 1.0:
            # Likely percentage value, convert to decimal
            trade_return = gain / 100.0
        else:
            trade_return = gain
        
        # Determine exit reason based on gain
        if trade_return > 0:
            exit_reason = "TP"
        elif trade_return < 0:
            exit_reason = "SL"
        else:
            exit_reason = "HORIZON"
        
        # Calculate profit
        position_size = equity * risk_per_trade
        profit = position_size * trade_return
        pnl_pct_trade = trade_return * 100.0  # Convert to percentage
        
        # Collect trade details
        trade_list.append({
            "trade_id": trade_id,
            "event_id": event_id,
            "entry_ts": entry_ts_str,
            "exit_reason": exit_reason,
            "pnl_pct": round(pnl_pct_trade, 4),
            "pnl_amount": round(profit, 4),
            "risk_effective": risk_per_trade,
        })
        
        equity = equity + profit
        equity_history.append(equity)
        
        trades += 1
        if trade_return > 0:
            wins += 1
    
    # Calculate results
    trade_count = trades
    win_rate = (wins / trade_count * 100.0) if trade_count > 0 else 0.0
    capital_end = equity
    pnl_pct = (capital_end / capital_start - 1.0) * 100.0
    max_dd_pct = compute_max_drawdown_pct(equity_history)
    
    # Compute trade_ids_hash
    trade_ids = sorted([t["trade_id"] for t in trade_list])
    trade_ids_hash = hashlib.sha1("".join(trade_ids).encode()).hexdigest()[:10] if trade_ids else "EMPTY"
    
    result = SniperBacktestResult(
        symbol=symbol,
        timeframe=timeframe,
        risk_per_trade=risk_per_trade,
        capital_start=round(capital_start, 2),
        capital_end=round(capital_end, 2),
        pnl_pct=round(pnl_pct, 2),
        trade_count=trade_count,
        win_rate=round(win_rate, 2),
        max_drawdown_pct=round(max_dd_pct, 2),
        selected_entries=selected_entries,
        total_entries=total_entries,
        entries_hash=entries_hash,
        trade_list=trade_list,
        trade_ids_hash=trade_ids_hash,
    )
    
    return result.to_dict()


# =============================================================================
# CLI
# =============================================================================

def main() -> None:
    """CLI entry point for sniper backtest."""
    import sys
    
    argv = sys.argv[1:]
    
    if not argv or argv[0] in ("-h", "--help"):
        print("🎯 Sniper Backtest v1")
        print("=" * 50)
        print()
        print("Usage:")
        print("  python -m tezaver.sniper.sniper_backtest SYMBOL TIMEFRAME [RISK]")
        print()
        print("Arguments:")
        print("  SYMBOL     Trading symbol (e.g., BTCUSDT)")
        print("  TIMEFRAME  Timeframe (e.g., 15m)")
        print("  RISK       Risk per trade (default: 1.0 = 100% equity)")
        print()
        print("Examples:")
        print("  python -m tezaver.sniper.sniper_backtest BTCUSDT 15m")
        print("  python -m tezaver.sniper.sniper_backtest BTCUSDT 15m 0.5")
        sys.exit(0)
    
    if len(argv) < 2:
        print("Error: SYMBOL and TIMEFRAME are required.")
        print("Use --help for usage information.")
        sys.exit(1)
    
    symbol = argv[0].upper()
    timeframe = argv[1]
    risk_per_trade = float(argv[2]) if len(argv) > 2 else 1.0
    
    try:
        result = run_sniper_backtest_for_symbol_timeframe(
            symbol=symbol,
            timeframe=timeframe,
            risk_per_trade=risk_per_trade,
        )
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
    
    # Print results
    print()
    print("-" * 60)
    print(f"🎯 Sniper Backtest v1 – {result['symbol']} {result['timeframe']}")
    print("-" * 60)
    print(f"Entries (toplam)  : {result['total_entries']}")
    print(f"Entries (seçilen) : {result['selected_entries']}")
    print(f"Trades            : {result['trade_count']}")
    print(f"Win Rate          : {result['win_rate']:.2f}%")
    print(f"💰 Sermaye        : {result['capital_start']:.2f} → {result['capital_end']:.2f} ({result['pnl_pct']:+.2f}%)")
    print(f"📉 Max Drawdown   : {result['max_drawdown_pct']:.2f}%")
    print(f"Risk / Trade      : {result['risk_per_trade']:.2f}x equity")
    print("-" * 60)


if __name__ == "__main__":
    main()
