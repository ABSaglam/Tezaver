"""
Snapshot Engine for Tezaver Mac.
Captures "pictures" (snapshots) of the market state when specific triggers occur.

Tezaver Philosophy:
- "Biz fiyatın anlık pozunu değil, oluşumun resmini saklarız."
- "Sadece kapanmış barlar kullanılır; geleceği görmeyiz."
- "Her snapshot, kapanmış bir barın ruh halini ve tetik anını temsil eder."
"""

import pandas as pd
from typing import List, Dict, Optional
from pathlib import Path
import sys

# Adjust path to allow imports if run directly or as module
from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

# --- Path Helpers ---

def get_patterns_root() -> Path:
    """
    Returns the root directory for pattern library.
    library/patterns/
    """
    project_root = coin_cell_paths.get_project_root()
    patterns_root = project_root / "library" / "patterns"
    if not patterns_root.exists():
        patterns_root.mkdir(parents=True, exist_ok=True)
    return patterns_root

def get_symbol_pattern_dir(symbol: str) -> Path:
    """
    Returns the pattern directory for a specific symbol.
    library/patterns/{SYMBOL}/
    """
    patterns_root = get_patterns_root()
    symbol_dir = patterns_root / symbol
    if not symbol_dir.exists():
        symbol_dir.mkdir(parents=True, exist_ok=True)
    return symbol_dir

def get_snapshot_file(symbol: str, timeframe: str) -> Path:
    """
    Returns the path to the snapshot parquet file.
    library/patterns/{SYMBOL}/snapshots_{TF}.parquet
    """
    symbol_dir = get_symbol_pattern_dir(symbol)
    filename = f"snapshots_{timeframe}.parquet"
    return symbol_dir / filename


# --- Trigger Logic ---

def build_default_triggers(df: pd.DataFrame) -> Dict[str, pd.Series]:
    """
    Builds default triggers based on features.
    Returns a dictionary of {trigger_name: boolean_series}.
    
    Triggers:
    - rsi_oversold: RSI < 30
    - rsi_overbought: RSI > 70
    - macd_bull_cross: MACD Line crosses above Signal Line
    - macd_bear_cross: MACD Line crosses below Signal Line
    - vol_spike: Volume Spike flag is active
    - vol_dry: Volume Dry flag is active
    
    Philosophy:
    "Bu tetikler, ahenk/ihanet analizine giden ilk ham taşlardır."
    """
    triggers = {}
    
    # RSI Triggers
    if "rsi" in df.columns:
        triggers["rsi_oversold"] = df["rsi"] < 30
        triggers["rsi_overbought"] = df["rsi"] > 70
        
    # MACD Triggers
    if "macd_line" in df.columns and "macd_signal" in df.columns:
        macd_line = df["macd_line"]
        macd_signal = df["macd_signal"]
        prev_line = macd_line.shift(1)
        prev_signal = macd_signal.shift(1)
        
        triggers["macd_bull_cross"] = (macd_line > macd_signal) & (prev_line <= prev_signal)
        triggers["macd_bear_cross"] = (macd_line < macd_signal) & (prev_line >= prev_signal)
        
    # Volume Triggers
    if "vol_spike" in df.columns:
        triggers["vol_spike"] = df["vol_spike"] == 1
        
    if "vol_dry" in df.columns:
        triggers["vol_dry"] = df["vol_dry"] == 1
        
    return triggers


# --- Core Snapshot Functions ---

def load_features(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Loads feature DataFrame for a symbol and timeframe.
    """
    data_dir = coin_cell_paths.get_coin_data_dir(symbol)
    feature_file = data_dir / f"features_{timeframe}.parquet"
    
    if not feature_file.exists():
        raise FileNotFoundError(f"Features not found for {symbol} {timeframe}. Run M3 feature build first.")
        
    return pd.read_parquet(feature_file)

def build_snapshots_for_symbol_timeframe(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Builds snapshots for a symbol and timeframe based on triggers.
    Saves the result to library/patterns/{SYMBOL}/snapshots_{TF}.parquet.
    """
    try:
        df_features = load_features(symbol, timeframe)
    except FileNotFoundError as e:
        print(e)
        return pd.DataFrame()
        
    if df_features.empty:
        print(f"Features empty for {symbol} {timeframe}")
        return pd.DataFrame()
        
    triggers = build_default_triggers(df_features)
    snapshots_list = []
    
    base_cols = [
        "symbol", "timeframe", "trigger",
        "timestamp", "datetime", "close",
        "rsi", "rsi_ema",
        "macd_line", "macd_signal", "macd_hist", "macd_phase",
        "atr",
        "ema_fast", "ema_mid", "ema_slow",
        "vol_rel", "vol_spike", "vol_dry",
    ]
    
    # Filter columns that actually exist in df_features
    available_cols = [c for c in base_cols if c in df_features.columns or c in ["symbol", "timeframe", "trigger"]]
    
    for trigger_name, mask in triggers.items():
        # Get rows where trigger is True
        df_trig = df_features[mask].copy()
        
        if df_trig.empty:
            continue
            
        # Add metadata columns
        df_trig["symbol"] = symbol
        df_trig["timeframe"] = timeframe
        df_trig["trigger"] = trigger_name
        
        # Select only relevant columns
        df_trig = df_trig[available_cols]
        snapshots_list.append(df_trig)
        
    if not snapshots_list:
        print(f"No snapshots generated for {symbol} {timeframe}")
        # Return empty DF with correct columns if possible, or just empty
        return pd.DataFrame(columns=available_cols)
        
    df_snapshots = pd.concat(snapshots_list, ignore_index=True)
    
    # Sort by timestamp to keep chronological order (mixed triggers)
    if "timestamp" in df_snapshots.columns:
        df_snapshots = df_snapshots.sort_values("timestamp").reset_index(drop=True)
        
    # Save
    snapshot_file = get_snapshot_file(symbol, timeframe)
    df_snapshots.to_parquet(snapshot_file, index=False)
    
    return df_snapshots

def bulk_build_snapshots(symbols: List[str], timeframes: List[str]) -> None:
    """
    Builds snapshots for multiple coins and timeframes.
    """
    for symbol in symbols:
        for tf in timeframes:
            try:
                print(f"Building snapshots for {symbol} {tf}...")
                build_snapshots_for_symbol_timeframe(symbol, tf)
            except Exception as e:
                print(f"Failed to build snapshots for {symbol} {tf}: {e}")
                continue
