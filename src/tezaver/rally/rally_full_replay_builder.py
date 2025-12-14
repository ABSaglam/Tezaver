"""
Tezaver Full Replay Dataset Builder
====================================

Builds bar-by-bar full replay datasets for Silver 15m War Game.
Merges price/feature data with pattern labels (sparse) on timestamp.

Output: data/replay/{symbol}/{timeframe}/full_replay_bars_v1.parquet
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
import pandas as pd

from tezaver.snapshots.snapshot_engine import load_features


# =============================================================================
# Loaders
# =============================================================================

def load_price_bars_for_symbol_timeframe(
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    """
    Load OHLCV + feature bars for a symbol and timeframe.
    
    Uses features_{tf}.parquet which contains:
    - timestamp, open, high, low, close, volume
    - rsi_15m (or rsi), rsi_ema_15m, volume_rel_15m, atr_pct_15m
    - Possibly macd, trend columns
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        
    Returns:
        DataFrame with OHLCV and feature columns.
        
    Raises:
        FileNotFoundError: If features file doesn't exist.
        
    TODO: Price_df içinde RSI/ATR/Volume feature'ları yoksa, 
          coin lab feature pipeline'ından türet.
    """
    df = load_features(symbol, timeframe)
    
    if df.empty:
        return df
    
    # Standardize timestamp column
    if "timestamp" not in df.columns:
        if "open_time" in df.columns:
            df["timestamp"] = df["open_time"]
        elif "datetime" in df.columns:
            df["timestamp"] = df["datetime"]
    
    # Ensure timestamp is pandas datetime
    if "timestamp" in df.columns:
        if not pd.api.types.is_datetime64_any_dtype(df["timestamp"]):
            # Check if ms timestamp
            if df["timestamp"].dtype in ["int64", "float64"]:
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
            else:
                df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    
    # Rename columns to standard names if needed
    rename_map = {}
    if "rsi" in df.columns and "rsi_15m" not in df.columns:
        rename_map["rsi"] = "rsi_15m"
    if "rsi_ema" in df.columns and "rsi_ema_15m" not in df.columns:
        rename_map["rsi_ema"] = "rsi_ema_15m"
    if "vol_rel" in df.columns and "volume_rel_15m" not in df.columns:
        rename_map["vol_rel"] = "volume_rel_15m"
    if "atr_pct" in df.columns and "atr_pct_15m" not in df.columns:
        rename_map["atr_pct"] = "atr_pct_15m"
    
    if rename_map:
        df = df.rename(columns=rename_map)
    
    return df


def load_pattern_labels_for_symbol_timeframe(
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    """
    Load label columns from rally_patterns_v1.parquet.
    
    These are sparse labels - only rally event rows have values,
    other rows will be NaN after join.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        
    Returns:
        DataFrame with: event_time, label_future_max_gain_pct, 
                       label_future_min_drawdown_pct, feat_quality_score, etc.
        
    Raises:
        FileNotFoundError: If pattern file doesn't exist.
    """
    parquet_path = Path(f"data/ai_datasets/{symbol}/{timeframe}/rally_patterns_v1.parquet")
    
    if not parquet_path.exists():
        raise FileNotFoundError(f"Pattern dataset not found: {parquet_path}")
    
    df = pd.read_parquet(parquet_path)
    
    # Convert event_time to timestamp for joining
    if "event_time" in df.columns:
        df["timestamp"] = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
    
    # Select relevant columns for labels
    label_cols = ["timestamp"]
    
    # Label columns
    if "label_future_max_gain_pct" in df.columns:
        label_cols.append("label_future_max_gain_pct")
    if "label_pre_peak_drawdown_pct" in df.columns:
        label_cols.append("label_pre_peak_drawdown_pct")
    elif "feat_pre_peak_drawdown_pct" in df.columns:
        label_cols.append("feat_pre_peak_drawdown_pct")
    
    # Quality score
    if "feat_quality_score" in df.columns:
        label_cols.append("feat_quality_score")
    
    # Bars to peak
    if "label_bars_to_peak" in df.columns:
        label_cols.append("label_bars_to_peak")
    elif "feat_bars_to_peak" in df.columns:
        label_cols.append("feat_bars_to_peak")
    
    # Grade labels (useful for filtering)
    for col in ["label_is_silver", "label_is_gold", "label_is_diamond"]:
        if col in df.columns:
            label_cols.append(col)
    
    return df[label_cols].copy()


# =============================================================================
# Builder
# =============================================================================

def build_full_replay_bars_for_symbol_timeframe(
    symbol: str,
    timeframe: str,
) -> pd.DataFrame:
    """
    Build full replay dataset by merging price bars with pattern labels.
    
    Steps:
    1. Load price/feature bars
    2. Load pattern labels (sparse)
    3. Left join on timestamp
    4. Normalize column names
    5. Sort by timestamp
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        
    Returns:
        DataFrame with all bars + sparse labels.
        
    TODO: Label'ları yalnızca Silver event bar'ları değil, 
          daha geniş bir candidate kümesi için üret.
    """
    # Load price bars
    price_df = load_price_bars_for_symbol_timeframe(symbol, timeframe)
    
    if price_df.empty:
        raise ValueError(f"Empty price data for {symbol} {timeframe}")
    
    # Load pattern labels
    try:
        labels_df = load_pattern_labels_for_symbol_timeframe(symbol, timeframe)
    except FileNotFoundError:
        # No patterns, just use price data with NaN labels
        labels_df = pd.DataFrame(columns=["timestamp"])
    
    # Left join on timestamp
    if not labels_df.empty and "timestamp" in labels_df.columns:
        # Drop duplicates in labels (in case multiple events on same bar)
        labels_df = labels_df.drop_duplicates(subset=["timestamp"], keep="first")
        
        # Merge
        full_df = price_df.merge(labels_df, on="timestamp", how="left")
    else:
        full_df = price_df.copy()
    
    # Normalize column names for ReplayDataFeed compatibility
    rename_map = {}
    
    # Timestamp
    if "timestamp" in full_df.columns:
        rename_map["timestamp"] = "ts"
    
    # Labels
    if "label_future_max_gain_pct" in full_df.columns:
        rename_map["label_future_max_gain_pct"] = "future_max_gain_pct"
    if "label_pre_peak_drawdown_pct" in full_df.columns:
        rename_map["label_pre_peak_drawdown_pct"] = "future_min_drawdown_pct"
    if "feat_pre_peak_drawdown_pct" in full_df.columns:
        rename_map["feat_pre_peak_drawdown_pct"] = "future_min_drawdown_pct"
    if "label_bars_to_peak" in full_df.columns:
        rename_map["label_bars_to_peak"] = "bars_to_peak"
    if "feat_bars_to_peak" in full_df.columns:
        rename_map["feat_bars_to_peak"] = "bars_to_peak"
    if "feat_quality_score" in full_df.columns:
        rename_map["feat_quality_score"] = "quality_score"
    
    if rename_map:
        full_df = full_df.rename(columns=rename_map)
    
    # Sort by timestamp
    if "ts" in full_df.columns:
        full_df = full_df.sort_values("ts").reset_index(drop=True)
    
    return full_df


def save_full_replay_bars_for_symbol_timeframe(
    symbol: str,
    timeframe: str,
    output_dir: Optional[Path] = None,
) -> Path:
    """
    Build and save full replay dataset to parquet.
    
    Args:
        symbol: Trading symbol (e.g., "BTCUSDT").
        timeframe: Timeframe (e.g., "15m").
        output_dir: Optional custom output directory.
                   Defaults to data/replay/{symbol}/{timeframe}/
        
    Returns:
        Path to the saved parquet file.
    """
    if output_dir is None:
        output_dir = Path(f"data/replay/{symbol}/{timeframe}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build dataset
    df = build_full_replay_bars_for_symbol_timeframe(symbol, timeframe)
    
    # Save to parquet
    parquet_path = output_dir / "full_replay_bars_v1.parquet"
    df.to_parquet(parquet_path, index=False)
    
    return parquet_path


def build_full_replay_bars_for_all_silver_15m() -> Dict[str, Path]:
    """
    Build full replay datasets for BTC, ETH, SOL 15m.
    
    Returns:
        Dict mapping symbol to saved parquet path.
    """
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    timeframe = "15m"
    
    results: Dict[str, Path] = {}
    
    for symbol in symbols:
        try:
            path = save_full_replay_bars_for_symbol_timeframe(symbol, timeframe)
            
            # Load to get stats
            df = pd.read_parquet(path)
            label_count = df["future_max_gain_pct"].notna().sum() if "future_max_gain_pct" in df.columns else 0
            
            print(f"[OK] {symbol} {timeframe}: {len(df)} bars, {label_count} labeled events")
            results[symbol] = path
            
        except FileNotFoundError as e:
            print(f"[SKIP] {symbol} {timeframe}: {e}")
        except ValueError as e:
            print(f"[SKIP] {symbol} {timeframe}: {e}")
    
    return results


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import sys
    
    # Usage:
    # python -m tezaver.rally.rally_full_replay_builder all
    # python -m tezaver.rally.rally_full_replay_builder BTCUSDT
    
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if cmd == "all":
        print("Building full replay datasets for Silver 15m...")
        result = build_full_replay_bars_for_all_silver_15m()
        print()
        print("Full replay datasets built:")
        for sym, path in result.items():
            print(f"  - {sym}: {path}")
    else:
        symbol = cmd
        print(f"Building full replay dataset for {symbol} 15m...")
        try:
            path = save_full_replay_bars_for_symbol_timeframe(symbol, "15m")
            print(f"[OK] Full replay dataset saved to: {path}")
        except Exception as e:
            print(f"[ERROR] {e}")
