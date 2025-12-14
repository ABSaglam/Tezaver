"""
Sniper Arena v4 - Entry Point
==============================

Single entry point for Sniper Arena with deterministic chain:
load → window → select → backtest

CLI: python -m tezaver.sniper.v4 BTCUSDT 15m --tightness 0 --risk 1.0
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import pandas as pd

from tezaver.sniper.v4.hashing_v4 import (
    compute_selection_fingerprint,
    compute_config_hash,
)
from tezaver.sniper.v4.select_v4 import (
    compute_dataset_stats,
    build_window,
    select_trade_ids,
    select_by_mode,
)
from tezaver.sniper.v4.backtest_v4 import run_backtest_from_trade_ids


# =============================================================================
# Constants
# =============================================================================

DATA_DIR = Path(__file__).parents[4] / "data"


def _get_card_path(symbol: str, timeframe: str) -> Path:
    """Get path to sniper strategy card."""
    paths = [
        DATA_DIR / "coin_profiles" / symbol / timeframe / "sniper_strategy_card_v1.json",
        DATA_DIR / "ai_datasets" / symbol / timeframe / "sniper_strategy_card_v1.json",
    ]
    for p in paths:
        if p.exists():
            return p
    return paths[0]  # Default to first path even if not exists


# =============================================================================
# Data Loading
# =============================================================================

def _to_iso(ts) -> str:
    """Convert timestamp to ISO format string."""
    if ts is None:
        return ""
    if isinstance(ts, str):
        return ts.replace(" ", "T")[:19]
    if isinstance(ts, pd.Timestamp):
        ts = ts.to_pydatetime()
    if isinstance(ts, datetime):
        return ts.replace(microsecond=0).isoformat()
    return str(ts)[:19]


def _ensure_trade_id(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has trade_id column."""
    if "trade_id" in df.columns:
        return df
    
    df = df.copy()
    
    # Find timestamp column
    ts_col = None
    for c in ["event_time", "entry_ts", "ts"]:
        if c in df.columns:
            ts_col = c
            break
    
    # Find ID column
    id_col = None
    for c in ["event_id", "entry_id", "event_idx"]:
        if c in df.columns:
            id_col = c
            break
    
    if id_col and ts_col:
        df["trade_id"] = df.apply(
            lambda r: f"{r[id_col]}|{_to_iso(r[ts_col])}", axis=1
        )
    elif ts_col:
        # Fallback: use index + timestamp
        df["trade_id"] = df.apply(
            lambda r: f"{r.name}|{_to_iso(r[ts_col])}", axis=1
        )
    else:
        # Last resort: use index
        df["trade_id"] = df.index.astype(str)
    
    return df


def load_dataset(symbol: str, timeframe: str, source: str = "patterns") -> pd.DataFrame:
    """
    Load sniper entries dataset.
    
    Args:
        symbol: Trading symbol (e.g., BTCUSDT)
        timeframe: Timeframe (e.g., 15m)
        source: "patterns" or "full_replay"
        
    Returns:
        DataFrame with trade_id column
    """
    symbol = symbol.upper()
    
    # Try primary paths
    paths = [
        DATA_DIR / "ai_datasets" / symbol / timeframe / "sniper_entries_v1.parquet",
        DATA_DIR / "sniper" / symbol / f"sniper_entries_{timeframe}_v1.parquet",
    ]
    
    for path in paths:
        if path.exists():
            df = pd.read_parquet(path)
            df = _ensure_trade_id(df)
            return df
    
    raise FileNotFoundError(
        f"Dataset not found. Tried: {[str(p) for p in paths]}"
    )


# =============================================================================
# Main Entry Point
# =============================================================================

def run_sniper_arena_v4(
    symbol: str,
    timeframe: str,
    source: str = "patterns",
    selection_mode: str = "ARENA_FILTERS",  # NEW: ARENA_FILTERS | CARD_STRICT_IDS | CARD_SOURCE_IDS
    tightness: int = 50,
    toggles: Optional[Dict[str, bool]] = None,
    risk: float = 0.01,
    tp_pct: float = 0.08,
    sl_pct: float = 0.03,
    sizing_mode: str = "equity_pct",
) -> Dict[str, Any]:
    """
    Run Sniper Arena v4.
    
    NON-NEGOTIABLE INVARIANTS:
    - Selected == Used == Trades
    - SelFP and PnLSig computed from actual trade set
    
    Args:
        symbol: Trading symbol
        timeframe: Timeframe
        source: Data source ("patterns" or "full_replay")
        selection_mode: "ARENA_FILTERS", "CARD_STRICT_IDS", or "CARD_SOURCE_IDS"
        tightness: 0-100 filter tightness (only for ARENA_FILTERS)
        toggles: Filter enable flags (only for ARENA_FILTERS)
        risk: Risk per trade as decimal
        tp_pct: Take profit as decimal
        sl_pct: Stop loss as decimal
        sizing_mode: "equity_pct" or "initial_notional"
        
    Returns:
        Result dict with proof fields
    """
    run_id = str(uuid4())[:8]
    symbol = symbol.upper()
    
    # Default toggles
    if toggles is None:
        toggles = {"rsi": True, "volume": True, "atr": True, "quality": True, "ml": False}
    
    # 1. Load dataset
    df = load_dataset(symbol, timeframe, source)
    total = len(df)
    
    # 2. Build filter window (only used for ARENA_FILTERS mode)
    stats = compute_dataset_stats(df)
    window = build_window(tightness, toggles, stats)
    
    # 3. Select trade IDs based on mode
    card_path = _get_card_path(symbol, timeframe)
    selected_ids = select_by_mode(
        df=df,
        mode=selection_mode,
        window=window,
        card_path=card_path if selection_mode != "ARENA_FILTERS" else None,
    )
    selected_count = len(selected_ids)
    
    # 4. Compute selection fingerprint
    sel_fp = compute_selection_fingerprint(selected_ids)
    
    # 5. Run backtest
    result = run_backtest_from_trade_ids(
        df=df,
        selected_trade_ids=selected_ids,
        risk=risk,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        sizing_mode=sizing_mode,
    )
    
    # 6. Compute config hash
    config = {
        "symbol": symbol,
        "timeframe": timeframe,
        "source": source,
        "selection_mode": selection_mode,
        "tightness": tightness,
        "toggles": toggles,
        "risk": risk,
        "tp_pct": tp_pct,
        "sl_pct": sl_pct,
        "sizing_mode": sizing_mode,
    }
    config_hash = compute_config_hash(config)
    
    # 7. Build proof line (includes mode)
    toggles_str = ",".join([k for k, v in toggles.items() if v])
    proof_line = (
        f"RUN={run_id} | Mode={selection_mode} | Selected={selected_count} Used={result.used_count} "
        f"Trades={result.trades} | SelFP={sel_fp} | PnLSig={result.pnl_signature} | "
        f"Cap=100→{result.capital_end:.0f} | Tightness={tightness} | Toggles={toggles_str}"
    )
    
    return {
        "run_id": run_id,
        "proof_line": proof_line,
        "symbol": symbol,
        "timeframe": timeframe,
        "source": source,
        "selection_mode": selection_mode,
        "total_entries": total,
        "selected_count": selected_count,
        "used_count": result.used_count,
        "trades": result.trades,
        "selection_fingerprint": sel_fp,
        "pnl_signature": result.pnl_signature,
        "capital_start": result.capital_start,
        "capital_end": result.capital_end,
        "pnl_pct": result.pnl_pct,
        "win_rate": result.win_rate,
        "exit_counts": result.exit_counts,
        "tightness": tightness,
        "toggles": toggles,
        "config_hash": config_hash,
        "window": window,
    }


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Sniper Arena v4")
    parser.add_argument("symbol", help="Trading symbol (e.g., BTCUSDT)")
    parser.add_argument("timeframe", help="Timeframe (e.g., 15m)")
    parser.add_argument("--source", default="patterns", choices=["patterns", "full_replay"])
    parser.add_argument("--tightness", type=int, default=50, help="0-100")
    parser.add_argument("--risk", type=float, default=0.01)
    parser.add_argument("--tp", type=float, default=0.08)
    parser.add_argument("--sl", type=float, default=0.03)
    parser.add_argument("--sizing", default="equity_pct", choices=["equity_pct", "initial_notional"])
    parser.add_argument("--no-rsi", action="store_true")
    parser.add_argument("--no-volume", action="store_true")
    parser.add_argument("--no-atr", action="store_true")
    parser.add_argument("--no-quality", action="store_true")
    
    args = parser.parse_args()
    
    toggles = {
        "rsi": not args.no_rsi,
        "volume": not args.no_volume,
        "atr": not args.no_atr,
        "quality": not args.no_quality,
        "ml": False,
    }
    
    result = run_sniper_arena_v4(
        symbol=args.symbol,
        timeframe=args.timeframe,
        source=args.source,
        tightness=args.tightness,
        toggles=toggles,
        risk=args.risk,
        tp_pct=args.tp,
        sl_pct=args.sl,
        sizing_mode=args.sizing,
    )
    
    print(result["proof_line"])
    print(f"\nExit Counts: {result['exit_counts']}")
    print(f"Window: {json.dumps(result['window'], indent=2, default=str)}")


if __name__ == "__main__":
    main()
