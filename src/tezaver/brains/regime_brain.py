"""
Regime Brain for Tezaver Mac.
Classifies coin behavior into market regimes.

Tezaver Philosophy:
- "Piyasa her zaman aynı şekilde nefes almaz; bazen sakin, bazen çalkantılı, bazen de likidite kuraklığı yaşar."
- "Regime, coin'in son dönem ruh halidir."
"""

import pandas as pd
import numpy as np
import json
from typing import List, Dict, Any
from pathlib import Path

from tezaver.core.coin_cell_paths import get_coin_data_dir
from tezaver.wisdom.pattern_stats import get_coin_profile_dir


def load_features_for_regime(symbol: str, timeframes: List[str]) -> List[pd.DataFrame]:
    """
    Loads feature DataFrames for regime analysis.
    """
    dfs = []
    data_dir = get_coin_data_dir(symbol)
    
    for tf in timeframes:
        file_path = data_dir / f"features_{tf}.parquet"
        if not file_path.exists():
            print(f"Warning: Features not found for {symbol} {tf}")
            continue
            
        try:
            df = pd.read_parquet(file_path)
            df["tf"] = tf  # Add timeframe label
            dfs.append(df)
        except Exception as e:
            print(f"Error loading features for {symbol} {tf}: {e}")
            continue
            
    return dfs


def compute_regime_metrics(symbol: str, timeframes: List[str] = ["4h", "1d"]) -> dict:
    """
    Computes regime classification metrics for a coin.
    
    Returns regime classification: "range_bound", "trending", "chaotic", "low_liquidity"
    """
    dfs = load_features_for_regime(symbol, timeframes)
    
    if not dfs:
        return {
            "symbol": symbol,
            "timeframes_used": timeframes,
            "regime": "unknown",
            "avg_atr_pct": None,
            "std_atr_pct": None,
            "trendiness_score": None,
            "chop_score": None,
            "low_liquidity_score": None
        }
    
    # Concatenate all timeframes
    df_all = pd.concat(dfs, ignore_index=True)
    
    # --- Compute Metrics ---
    
    # ATR %
    atr_pct_values = []
    if "atr" in df_all.columns and "close" in df_all.columns:
        atr_series = df_all["atr"].dropna()
        close_series = df_all.loc[atr_series.index, "close"].replace(0, pd.NA)
        atr_pct_series = (atr_series / close_series).dropna()
        atr_pct_values = atr_pct_series.tolist()
    
    avg_atr_pct = float(np.mean(atr_pct_values)) if atr_pct_values else None
    std_atr_pct = float(np.std(atr_pct_values)) if atr_pct_values else None
    
    # Volume Rel
    avg_vol_rel = None
    if "vol_rel" in df_all.columns:
        avg_vol_rel = float(df_all["vol_rel"].mean())
    
    # Trendiness Score
    # Based on EMA separation
    trendiness_score = 0.0
    if "ema_fast" in df_all.columns and "ema_slow" in df_all.columns and "close" in df_all.columns:
        df_trend = df_all[["ema_fast", "ema_slow", "close"]].dropna()
        if not df_trend.empty:
            ema_sep = np.abs(df_trend["ema_fast"] - df_trend["ema_slow"]) / df_trend["close"]
            trendiness_score = float(ema_sep.mean())
    
    # Chop Score
    # Based on MACD phase flips
    chop_score = 0.0
    if "macd_phase" in df_all.columns:
        # Count phase changes
        phases = df_all["macd_phase"].dropna()
        if len(phases) > 1:
            phase_changes = (phases != phases.shift(1)).sum()
            chop_score = float(phase_changes / len(phases))
    
    # Low Liquidity Score
    low_liquidity_score = 0.0
    if "vol_dry" in df_all.columns:
        vol_dry = df_all["vol_dry"].dropna()
        if len(vol_dry) > 0:
            low_liquidity_score = float((vol_dry == 1).mean())
    
    # --- Determine Regime ---
    regime = "unknown"
    
    if low_liquidity_score > 0.4:
        regime = "low_liquidity"
    elif avg_atr_pct is not None and trendiness_score is not None:
        # Range bound: low volatility, low trend
        if avg_atr_pct < 0.01 and trendiness_score < 0.02 and chop_score < 0.3:
            regime = "range_bound"
        # Trending: high trend, low chop
        elif trendiness_score > 0.03 and chop_score < 0.3:
            regime = "trending"
        # Chaotic: everything else (high chop or high vol with low trend)
        else:
            regime = "chaotic"
    
    return {
        "symbol": symbol,
        "timeframes_used": timeframes,
        "regime": regime,
        "avg_atr_pct": avg_atr_pct,
        "std_atr_pct": std_atr_pct,
        "avg_vol_rel": avg_vol_rel,
        "trendiness_score": trendiness_score,
        "chop_score": chop_score,
        "low_liquidity_score": low_liquidity_score
    }


def save_regime_profile(symbol: str, profile: dict) -> None:
    """
    Saves regime profile to JSON.
    """
    profile_dir = get_coin_profile_dir(symbol)
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    path = profile_dir / "regime_profile.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    
    print(f"  Saved regime profile for {symbol} to {path}")


def build_regime_profiles(symbols: List[str], timeframes: List[str] = ["4h", "1d"]) -> None:
    """
    Builds regime profiles for multiple symbols.
    """
    for symbol in symbols:
        print(f"Building regime profile for {symbol}...")
        try:
            profile = compute_regime_metrics(symbol, timeframes)
            save_regime_profile(symbol, profile)
        except Exception as e:
            print(f"Error building regime profile for {symbol}: {e}")
            import traceback
            traceback.print_exc()
