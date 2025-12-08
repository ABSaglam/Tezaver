"""
Shock Brain for Tezaver Mac.
Detects shock/manipulation-like candles.

Tezaver Philosophy:
- "Büyük mum + hacim patlaması = birilerinin kalabalığı korkutma veya FOMO'ya sürükleme çabası."
- "Shock candles, piyasanın doğal akışının dışında, ani ve sert hareketlerdir."
"""

import pandas as pd
import numpy as np
import json
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime

from tezaver.core.coin_cell_paths import get_coin_data_dir
from tezaver.wisdom.pattern_stats import get_coin_profile_dir


def detect_shocks_for_symbol(symbol: str, timeframes: List[str] = ["1h", "4h"]) -> dict:
    """
    Detects shock candles for a symbol.
    
    Shock criteria:
    - Large range (high-low) relative to typical range
    - Volume spike (if available)
    """
    data_dir = get_coin_data_dir(symbol)
    
    total_bars = 0
    total_shocks = 0
    shock_ranges = []
    last_shock_dt = None
    
    for tf in timeframes:
        file_path = data_dir / f"features_{tf}.parquet"
        if not file_path.exists():
            print(f"Warning: Features not found for {symbol} {tf}")
            continue
            
        try:
            df = pd.read_parquet(file_path)
        except Exception as e:
            print(f"Error loading features for {symbol} {tf}: {e}")
            continue
        
        if df.empty:
            continue
        
        # Compute range_pct
        if "high" in df.columns and "low" in df.columns and "close" in df.columns:
            df["range_pct"] = (df["high"] - df["low"]) / df["close"].replace(0, pd.NA)
            df["range_pct"] = df["range_pct"].fillna(0)
        else:
            continue
        
        # Define shock threshold: 3x median range
        median_range = df["range_pct"].median()
        shock_threshold = median_range * 3.0
        
        # Shock condition
        shock_mask = df["range_pct"] > shock_threshold
        
        # If vol_spike exists, require it as well
        if "vol_spike" in df.columns:
            shock_mask = shock_mask & (df["vol_spike"] == 1)
        
        # Count shocks
        shocks_in_tf = shock_mask.sum()
        total_shocks += shocks_in_tf
        total_bars += len(df)
        
        # Collect shock ranges
        shock_ranges.extend(df.loc[shock_mask, "range_pct"].tolist())
        
        # Find last shock datetime
        if shocks_in_tf > 0 and "datetime" in df.columns:
            shock_dates = pd.to_datetime(df.loc[shock_mask, "datetime"])
            if not shock_dates.empty:
                max_shock_dt = shock_dates.max()
                if last_shock_dt is None or max_shock_dt > last_shock_dt:
                    last_shock_dt = max_shock_dt
    
    # Compute metrics
    shock_freq = total_shocks / total_bars if total_bars > 0 else 0.0
    avg_shock_range_pct = float(np.mean(shock_ranges)) if shock_ranges else None
    last_shock_datetime_str = last_shock_dt.isoformat() if last_shock_dt is not None else None
    
    return {
        "symbol": symbol,
        "timeframes_used": timeframes,
        "shock_freq": float(shock_freq),
        "avg_shock_range_pct": avg_shock_range_pct,
        "total_shocks": int(total_shocks),
        "total_bars": int(total_bars),
        "last_shock_datetime": last_shock_datetime_str
    }


def save_shock_profile(symbol: str, profile: dict) -> None:
    """
    Saves shock profile to JSON.
    """
    profile_dir = get_coin_profile_dir(symbol)
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    path = profile_dir / "shock_profile.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    
    print(f"  Saved shock profile for {symbol} to {path}")


def build_shock_profiles(symbols: List[str], timeframes: List[str] = ["1h", "4h"]) -> None:
    """
    Builds shock profiles for multiple symbols.
    """
    for symbol in symbols:
        print(f"Building shock profile for {symbol}...")
        try:
            profile = detect_shocks_for_symbol(symbol, timeframes)
            save_shock_profile(symbol, profile)
        except Exception as e:
            print(f"Error building shock profile for {symbol}: {e}")
            import traceback
            traceback.print_exc()
