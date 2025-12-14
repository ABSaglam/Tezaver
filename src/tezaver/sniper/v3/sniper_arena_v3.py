"""
Sniper Arena v3
===============

Clean, single-purpose arena runner with strict invariants:
- Single trade_id format: "{event_id}|{entry_ts_iso}"
- unique_count == selected_count (RuntimeError if duplicates)
- All selection in one place
- debug_stage_counts for filter transparency
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pandas as pd

from tezaver.sniper.sniper_filter_debug import (
    build_effective_sniper_filter_window,
    compute_sniper_dataset_stats,
    SniperDatasetStats,
)
from tezaver.sniper.v3.sniper_backtest_v3 import run_backtest_v3_from_trade_ids


# =============================================================================
# Constants
# =============================================================================

# Path: v3/sniper_arena_v3.py -> sniper -> tezaver -> src -> TezaverMac -> data
DATA_DIR = Path(__file__).parents[4] / "data"


# =============================================================================
# Helpers
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


def _make_trade_id(event_id, entry_ts) -> str:
    """Create unique trade_id: '{event_id}|{entry_ts_iso}'"""
    return f"{event_id}|{_to_iso(entry_ts)}"


def _ensure_trade_id_column(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure DataFrame has trade_id column."""
    if "trade_id" in df.columns:
        return df
    
    ts_col = None
    for c in ["entry_ts", "event_time", "ts"]:
        if c in df.columns:
            ts_col = c
            break
    
    id_col = None
    for c in ["event_id", "entry_id", "event_idx"]:
        if c in df.columns:
            id_col = c
            break
    
    if id_col and ts_col:
        df = df.copy()
        df["trade_id"] = df.apply(
            lambda r: _make_trade_id(r[id_col], r[ts_col]), axis=1
        )
    elif ts_col:
        # Fallback: use index + timestamp
        df = df.copy()
        df["trade_id"] = df.apply(
            lambda r: _make_trade_id(r.name, r[ts_col]), axis=1
        )
    
    return df



def _load_sniper_dataset(symbol: str, timeframe: str) -> pd.DataFrame:
    """Load sniper entries dataset."""
    symbol = symbol.upper()
    
    # Primary path: ai_datasets location
    path = DATA_DIR / "ai_datasets" / symbol / timeframe / "sniper_entries_v1.parquet"
    
    # Fallback: old sniper location
    if not path.exists():
        path = DATA_DIR / "sniper" / symbol / f"sniper_entries_{timeframe}_v1.parquet"
    
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    
    df = pd.read_parquet(path)
    df = _ensure_trade_id_column(df)
    return df


def _load_strategy_card(symbol: str, timeframe: str) -> Dict[str, Any]:
    """Load strategy card or return empty config."""
    symbol = symbol.upper()
    
    # Primary path: ai_datasets location
    path = DATA_DIR / "ai_datasets" / symbol / timeframe / "sniper_strategy_card_v1.json"
    
    # Fallback: old sniper location
    if not path.exists():
        path = DATA_DIR / "sniper" / symbol / f"sniper_strategy_card_{timeframe}_v1.json"
    
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    
    return {"entry_filters": {}, "labels": {}}



# =============================================================================
# Main Function
# =============================================================================

def run_sniper_arena_v3(
    symbol: str,
    timeframe: str,
    data_source: str = "patterns",  # For future: patterns/full_replay
    tightness: int = 50,
    toggles: Optional[Dict[str, bool]] = None,
    clamp_policy: str = "HARD",  # OFF/SOFT/HARD
    quality_min_override: Optional[float] = None,
    mode: str = "experiment",  # contract/experiment
    risk: float = 0.01,
    tp_pct: float = 0.08,
    sl_pct: float = 0.03,
    max_bars: int = 20,
    pnl_mode: str = "TPSL",  # RAW/TPSL
) -> Dict[str, Any]:
    """
    Run Sniper Arena v3 with strict invariants.
    
    NON-NEGOTIABLE:
    - unique_count == selected_count (RuntimeError if duplicates)
    - Backtest: used_count == selected_count == trades
    
    Returns:
        Comprehensive result with fingerprints, debug_stage_counts, and backtest.
    """
    symbol = symbol.upper()
    run_id = str(uuid4())[:8]
    computed_at = datetime.now().isoformat()[:19]
    
    # Default toggles
    if toggles is None:
        toggles = {"rsi": True, "volume": True, "atr": True, "quality": True, "ml": False}
    
    # =========================================================================
    # 1. Load Dataset
    # =========================================================================
    df = _load_sniper_dataset(symbol, timeframe)
    total_entries = len(df)
    
    if total_entries == 0:
        raise ValueError(f"Empty dataset for {symbol} {timeframe}")
    
    # =========================================================================
    # 2. Load Strategy Card
    # =========================================================================
    card = _load_strategy_card(symbol, timeframe)
    
    # =========================================================================
    # 3. Compute Dataset Stats
    # =========================================================================
    dataset_stats = compute_sniper_dataset_stats(df)

    
    # =========================================================================
    # 4. Build Effective Window
    # =========================================================================
    effective_window = build_effective_sniper_filter_window(
        profile_cfg=card,
        tightness=tightness,
        toggles=toggles,
        dataset_stats=dataset_stats,
        clamp_policy=clamp_policy,
        quality_override=quality_min_override,
    )
    
    # Compute window hash
    window_json = json.dumps(effective_window, sort_keys=True, default=str)
    window_hash = hashlib.sha1(window_json.encode()).hexdigest()[:10]
    
    # =========================================================================
    # 5. Apply Filters Stage by Stage (with debug counts)
    # =========================================================================
    debug_stage_counts = {"TOTAL": total_entries}
    df_filtered = df.copy()
    
    # RSI filter
    if toggles.get("rsi", True):
        rsi_cfg = effective_window.get("effective_rsi", {})
        if rsi_cfg.get("enabled", True) and "rsi" in df_filtered.columns:
            rsi_min = rsi_cfg.get("min", 0)
            rsi_max = rsi_cfg.get("max", 100)
            df_filtered = df_filtered[
                (df_filtered["rsi"] >= rsi_min) & (df_filtered["rsi"] <= rsi_max)
            ]
    debug_stage_counts["RSI"] = len(df_filtered)
    
    # Volume filter
    if toggles.get("volume", True):
        vol_cfg = effective_window.get("effective_volume", {})
        if vol_cfg.get("enabled", True) and "volume_ratio" in df_filtered.columns:
            vol_min = vol_cfg.get("min", 0)
            vol_max = vol_cfg.get("max", 999999)
            df_filtered = df_filtered[
                (df_filtered["volume_ratio"] >= vol_min) & 
                (df_filtered["volume_ratio"] <= vol_max)
            ]
    debug_stage_counts["VOLUME"] = len(df_filtered)
    
    # ATR filter
    if toggles.get("atr", True):
        atr_cfg = effective_window.get("effective_atr", {})
        if atr_cfg.get("enabled", True) and "atr" in df_filtered.columns:
            atr_min = atr_cfg.get("min", 0)
            atr_max = atr_cfg.get("max", 999999)
            df_filtered = df_filtered[
                (df_filtered["atr"] >= atr_min) & (df_filtered["atr"] <= atr_max)
            ]
    debug_stage_counts["ATR"] = len(df_filtered)
    
    # Quality filter
    if toggles.get("quality", True):
        q_cfg = effective_window.get("effective_quality", {})
        if q_cfg.get("enabled", True) and "quality_score" in df_filtered.columns:
            q_min = q_cfg.get("min", 0)
            df_filtered = df_filtered[df_filtered["quality_score"] >= q_min]
    debug_stage_counts["QUALITY"] = len(df_filtered)
    
    # ML filter (placeholder)
    if toggles.get("ml", False):
        # Future: apply ML filter
        pass
    debug_stage_counts["ML"] = len(df_filtered)
    
    # =========================================================================
    # 6. Extract Selected Trade IDs
    # =========================================================================
    selected_trade_ids = df_filtered["trade_id"].tolist()
    selected_count = len(selected_trade_ids)
    unique_trade_ids = sorted(set(selected_trade_ids))
    unique_count = len(unique_trade_ids)
    
    # INVARIANT: No duplicates allowed
    if unique_count != selected_count:
        from collections import Counter
        c = Counter(selected_trade_ids)
        dups = [k for k, v in c.items() if v > 1][:10]
        raise RuntimeError(
            f"[V3_DUPLICATE_IDS] selected={selected_count} unique={unique_count} "
            f"dup_sample={dups}"
        )
    
    # Compute selection fingerprint
    sel_fingerprint = hashlib.sha1("|".join(unique_trade_ids).encode()).hexdigest()[:12]
    
    # =========================================================================
    # 7. Compute Config Hash
    # =========================================================================
    config_dict = {
        "symbol": symbol,
        "timeframe": timeframe,
        "tightness": tightness,
        "toggles": toggles,
        "clamp_policy": clamp_policy,
        "quality_min_override": quality_min_override,
        "mode": mode,
        "risk": risk,
        "tp_pct": tp_pct,
        "sl_pct": sl_pct,
        "max_bars": max_bars,
        "pnl_mode": pnl_mode,
    }
    config_json = json.dumps(config_dict, sort_keys=True, default=str)
    config_hash = hashlib.sha1(config_json.encode()).hexdigest()[:10]
    
    # =========================================================================
    # 8. Run Backtest
    # =========================================================================
    backtest_result = run_backtest_v3_from_trade_ids(
        df=df,  # Full dataset with trade_id column
        selected_trade_ids=unique_trade_ids,
        risk=risk,
        mode=mode,
        max_risk=0.02 if mode == "contract" else None,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        max_bars=max_bars,
        pnl_mode=pnl_mode,
    )
    
    # =========================================================================
    # 9. Build Result
    # =========================================================================
    return {
        # Run info
        "run_id": run_id,
        "computed_at": computed_at,
        
        # Selection (guaranteed: selected == unique)
        "selected_count": selected_count,
        "unique_count": unique_count,
        "selected_trade_ids": unique_trade_ids,
        "selection_fingerprint": sel_fingerprint,
        
        # Hashes
        "window_hash": window_hash,
        "config_hash": config_hash,
        
        # Debug
        "debug_stage_counts": debug_stage_counts,
        "total_entries": total_entries,
        "effective_window": effective_window,
        
        # Backtest (guaranteed: used == selected == trades)
        "backtest": backtest_result,
        
        # Convenience copies
        "trades": backtest_result["trades"],
        "capital_end": backtest_result["capital_end"],
        "pnl_pct": backtest_result["pnl_pct"],
        "pnl_signature_v2": backtest_result["pnl_signature_v2"],
        "top_pnl_bins": backtest_result["top_pnl_bins"],
        
        # Mode info
        "pnl_mode": pnl_mode,
        "tightness": tightness,
        "clamp_policy": clamp_policy,
    }
