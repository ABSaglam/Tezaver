"""
Sniper Story Builder - ML Dataset from Sniper Annotations
==========================================================

Builds rich ML datasets from sniper annotations:
- Joins sniper entry points with pattern labels
- Enriches with full replay bar features
- Outputs parquet + meta JSON

Output: data/ai_datasets/{symbol}/{timeframe}/sniper_entries_v1.parquet
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
import json
import datetime

import pandas as pd

from tezaver.sniper.sniper_annotations import SniperAnnotationRepository, SniperAnnotation
from tezaver.rally.rally_pattern_loader import load_silver_15m_patterns


# =============================================================================
# Helper Functions
# =============================================================================

def _load_full_replay_df(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Load full replay dataset for a symbol/timeframe.
    
    Path: data/replay/{symbol}/{timeframe}/full_replay_bars_v1.parquet
    
    Returns:
        DataFrame with ts, bar_index, and all feature columns.
    """
    symbol = symbol.upper()
    path = Path(f"data/replay/{symbol}/{timeframe}/full_replay_bars_v1.parquet")
    
    if not path.exists():
        raise FileNotFoundError(
            f"Full replay dataset not found: {path}. "
            "Run 'python -m tezaver.rally.rally_full_replay_builder all' first."
        )
    
    df = pd.read_parquet(path)
    
    # Normalize timestamp column
    ts_col = None
    for c in ["ts", "timestamp", "open_time"]:
        if c in df.columns:
            ts_col = c
            break
    
    if ts_col is None:
        raise ValueError(f"Full replay DF must contain a time column. Found: {df.columns.tolist()}")
    
    df["ts"] = pd.to_datetime(df[ts_col], utc=True, errors="coerce")
    df = df.sort_values("ts").reset_index(drop=True)
    df["bar_index"] = df.index
    
    return df


def _find_event_id_column(df: pd.DataFrame) -> Optional[str]:
    """Find the event ID column in a DataFrame."""
    for candidate in ["event_id", "rally_id", "pattern_id"]:
        if candidate in df.columns:
            return candidate
    return None


def _find_timestamp_column(df: pd.DataFrame) -> Optional[str]:
    """Find the timestamp column in a DataFrame."""
    for candidate in ["event_time", "start_ts", "ts", "timestamp"]:
        if candidate in df.columns:
            return candidate
    return None


# =============================================================================
# Main Builder
# =============================================================================

def build_sniper_entry_dataset_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Build sniper entry dataset from annotations + patterns + full replay.
    
    Steps:
    1. Load sniper annotations
    2. Load Silver pattern dataset
    3. Load full replay bar dataset
    4. For each annotation, find entry bar and extract features
    5. Return DataFrame + meta dict
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        
    Returns:
        Tuple of (DataFrame, meta dict).
        
    Raises:
        RuntimeError: If no annotations found or no entries resolved.
    """
    symbol = symbol.upper()
    repo = SniperAnnotationRepository()
    annotations = repo.load_all(symbol, timeframe)

    if not annotations:
        raise RuntimeError(
            f"No sniper annotations found for {symbol} {timeframe}. "
            "Önce Sniper Lab'te en az 1 entry işaretle."
        )

    # Load pattern dataset (silver)
    patterns_df = load_silver_15m_patterns(symbol)
    
    # Find event_id column
    event_id_col = _find_event_id_column(patterns_df)
    if event_id_col is None:
        # Create synthetic event_id from index
        patterns_df = patterns_df.reset_index(drop=True)
        patterns_df["event_id"] = patterns_df.index.astype(str)
        event_id_col = "event_id"

    # Find timestamp column
    ts_col = _find_timestamp_column(patterns_df)
    if ts_col is None:
        raise ValueError(
            "Pattern dataset must contain a timestamp column "
            f"(event_time, start_ts, ts). Found: {patterns_df.columns.tolist()}"
        )
    
    patterns_df["pattern_ts"] = pd.to_datetime(patterns_df[ts_col], utc=True, errors="coerce")

    # Find label columns
    gain_col = None
    for c in ["label_future_max_gain_pct", "future_max_gain_pct", "gain_pct"]:
        if c in patterns_df.columns:
            gain_col = c
            break
    
    dd_col = None
    for c in ["label_pre_peak_drawdown_pct", "future_min_drawdown_pct", "pre_peak_dd_pct"]:
        if c in patterns_df.columns:
            dd_col = c
            break

    silver_col = None
    for c in ["label_is_silver", "is_silver"]:
        if c in patterns_df.columns:
            silver_col = c
            break
    
    quality_col = None
    for c in ["feat_quality_score", "quality_score"]:
        if c in patterns_df.columns:
            quality_col = c
            break

    bars_to_peak_col = None
    for c in ["label_bars_to_peak", "bars_to_peak"]:
        if c in patterns_df.columns:
            bars_to_peak_col = c
            break

    # Load full replay DF
    full_df = _load_full_replay_df(symbol, timeframe)
    
    # Create ts -> bar_index mapping
    ts_to_index = dict(zip(full_df["ts"], full_df["bar_index"]))

    records: List[Dict[str, Any]] = []

    for ann in annotations:
        # Find matching pattern row
        p_mask = patterns_df[event_id_col].astype(str) == str(ann.event_id)
        if not p_mask.any():
            # Event ID not in patterns, skip
            continue
        
        p_row = patterns_df[p_mask].iloc[0]
        pattern_ts = p_row["pattern_ts"]
        
        # Find start bar in full replay
        if pd.isna(pattern_ts):
            continue
        
        # Find closest matching timestamp
        start_bar_index = None
        if pattern_ts in ts_to_index:
            start_bar_index = ts_to_index[pattern_ts]
        else:
            # Try to find nearest timestamp
            ts_diffs = abs(full_df["ts"] - pattern_ts)
            min_idx = ts_diffs.idxmin()
            if ts_diffs.iloc[min_idx] < pd.Timedelta(minutes=20):
                start_bar_index = int(full_df.loc[min_idx, "bar_index"])
        
        if start_bar_index is None:
            continue

        # Calculate entry bar index
        entry_index = start_bar_index + int(ann.entry_bar_offset)
        
        # Check bounds
        if entry_index < 0 or entry_index >= len(full_df):
            continue

        # Get entry bar data
        entry_row = full_df.iloc[entry_index]
        entry_ts = entry_row["ts"]

        # Build record
        base: Dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "event_id": str(ann.event_id),
            "entry_ts": entry_ts.isoformat() if hasattr(entry_ts, 'isoformat') else str(entry_ts),
            "entry_bar_index": int(entry_index),
            "entry_bar_offset": int(ann.entry_bar_offset),
            "sniper_note": ann.note,
            "sniper_created_at": ann.created_at,
        }

        # Add label columns from pattern
        if gain_col and gain_col in p_row.index:
            val = p_row[gain_col]
            base["future_max_gain_pct"] = float(val) if pd.notna(val) else None
        else:
            base["future_max_gain_pct"] = None

        if dd_col and dd_col in p_row.index:
            val = p_row[dd_col]
            base["future_min_drawdown_pct"] = float(val) if pd.notna(val) else None
        else:
            base["future_min_drawdown_pct"] = None

        if silver_col and silver_col in p_row.index:
            val = p_row[silver_col]
            base["is_silver"] = int(val) if pd.notna(val) else None
        else:
            base["is_silver"] = None
            
        if quality_col and quality_col in p_row.index:
            val = p_row[quality_col]
            base["quality_score"] = float(val) if pd.notna(val) else None
        else:
            base["quality_score"] = None
            
        if bars_to_peak_col and bars_to_peak_col in p_row.index:
            val = p_row[bars_to_peak_col]
            base["bars_to_peak"] = int(val) if pd.notna(val) else None
        else:
            base["bars_to_peak"] = None

        # Add feature columns from full replay entry bar
        skip_cols = {"ts", "bar_index", "timestamp", "open_time"}
        for col in entry_row.index:
            if col in skip_cols:
                continue
            if col in base:
                continue  # Already added
            
            val = entry_row[col]
            if pd.isna(val):
                base[col] = None
            elif isinstance(val, (int, float)):
                base[col] = float(val) if isinstance(val, float) else int(val)
            else:
                try:
                    base[col] = float(val)
                except (ValueError, TypeError):
                    base[col] = str(val)

        records.append(base)

    if not records:
        raise RuntimeError(
            f"No sniper entries could be resolved for {symbol} {timeframe}. "
            "Event-id eşleşmeleri veya full replay join sorunlu olabilir."
        )

    df_out = pd.DataFrame(records)

    # Build meta
    meta_cols = [
        "symbol", "timeframe", "event_id", "entry_ts", "entry_bar_index",
        "entry_bar_offset", "sniper_note", "sniper_created_at",
        "future_max_gain_pct", "future_min_drawdown_pct", "is_silver",
        "quality_score", "bars_to_peak",
    ]
    feature_columns = [c for c in df_out.columns if c not in meta_cols]

    meta: Dict[str, Any] = {
        "symbol": symbol,
        "timeframe": timeframe,
        "version": "sniper_entries_v1",
        "built_at": datetime.datetime.utcnow().isoformat(),
        "num_entries": len(df_out),
        "num_features": len(feature_columns),
        "feature_columns": feature_columns,
    }

    # Add date range
    try:
        ts_series = pd.to_datetime(df_out["entry_ts"])
        meta["entry_start"] = ts_series.min().isoformat()
        meta["entry_end"] = ts_series.max().isoformat()
    except Exception:
        meta["entry_start"] = None
        meta["entry_end"] = None

    return df_out, meta


# =============================================================================
# Save Helpers
# =============================================================================

def save_sniper_entry_dataset_for_symbol_timeframe(
    symbol: str,
    timeframe: str = "15m",
) -> Path:
    """
    Build and save sniper entry dataset to parquet + meta JSON.
    
    Args:
        symbol: Trading symbol.
        timeframe: Timeframe.
        
    Returns:
        Path to saved parquet file.
    """
    df, meta = build_sniper_entry_dataset_for_symbol_timeframe(symbol, timeframe)

    base_dir = Path("data/ai_datasets") / symbol.upper() / timeframe
    base_dir.mkdir(parents=True, exist_ok=True)

    parquet_path = base_dir / "sniper_entries_v1.parquet"
    meta_path = base_dir / "sniper_entries_v1_meta.json"

    df.to_parquet(parquet_path, index=False)

    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[OK] Saved {len(df)} sniper entries for {symbol} {timeframe}")
    print(f"     Parquet: {parquet_path}")
    print(f"     Meta: {meta_path}")
    
    return parquet_path


def build_sniper_entry_datasets_for_all_silver_15m_symbols() -> Dict[str, Path]:
    """
    Build sniper entry datasets for all Silver 15m symbols.
    
    Returns:
        Dict mapping symbol to saved parquet path.
    """
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    results: Dict[str, Path] = {}
    
    for sym in symbols:
        try:
            path = save_sniper_entry_dataset_for_symbol_timeframe(sym, "15m")
            results[sym] = path
        except RuntimeError as e:
            print(f"[SKIP] {sym}: {e}")
        except FileNotFoundError as e:
            print(f"[SKIP] {sym}: {e}")
        except Exception as e:
            print(f"[ERROR] {sym}: {e}")
    
    return results
