"""
Indicator Engine for Tezaver Mac.
Calculates technical indicators (RSI, MACD, ATR, EMA, Volume) from historical data.

Tezaver Philosophy:
- "Trend yön değil, ruh hâlidir." -> RSI/MACD/EMA bu ruhu okumak için kullanılır.
- "Hacim hareketin samimiyetini ifşa eder." -> vol_spike ve vol_dry buna hizmet eder.
- "Tüm hesaplamalar kapanmış barlar üzerinde yapılır." -> Geleceği görmeyiz, geleceğe ihanet etmeyiz.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from pathlib import Path
import sys

# Adjust path to allow imports if run directly or as module
# Assuming standard structure
from tezaver.core import coin_cell_paths
from tezaver.data import history_service

# --- Configuration ---
from tezaver.core.config import (
    RSI_PERIOD, RSI_EMA_PERIOD,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    ATR_PERIOD
)

# --- Configuration ---
# Defaults are now loaded from core.config
EMA_FAST = 20
EMA_MID = 50
EMA_SLOW = 200
VOL_WINDOW = 20
VOL_SPIKE_THRESHOLD = 2.0
VOL_DRY_THRESHOLD = 0.5


# --- Indicator Functions ---

def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """
    Calculates RSI using EMA smoothing.
    Returns 0-100 value.
    """
    diff = close.diff()
    gain = diff.where(diff > 0, 0)
    loss = -diff.where(diff < 0, 0)
    
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def compute_macd(
    close: pd.Series, 
    fast: int = MACD_FAST, 
    slow: int = MACD_SLOW, 
    signal: int = MACD_SIGNAL
) -> Dict[str, pd.Series]:
    """
    Calculates MACD line, Signal line, and Histogram.
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    
    return {
        "macd_line": macd_line,
        "macd_signal": signal_line,
        "macd_hist": hist,
    }

def assign_macd_phase(hist: pd.Series) -> pd.Series:
    """
    Determines the phase of the MACD histogram.
    - bull_build: Positive and growing
    - bull_fade: Positive but shrinking
    - bear_build: Negative and growing (downwards)
    - bear_fade: Negative but shrinking (upwards)
    """
    prev_hist = hist.shift(1)
    
    conditions = [
        (hist > 0) & (hist > prev_hist),
        (hist > 0) & (hist <= prev_hist),
        (hist < 0) & (hist < prev_hist),
        (hist < 0) & (hist >= prev_hist)
    ]
    choices = ["bull_build", "bull_fade", "bear_build", "bear_fade"]
    
    # Use numpy select or map, but pandas apply/numpy where is easier for Series
    # Let's use numpy select for vectorization
    import numpy as np
    phase = np.select(conditions, choices, default="flat")
    return pd.Series(phase, index=hist.index)

def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    """
    Calculates Average True Range (ATR).
    Requires 'high', 'low', 'close' columns.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1/period, adjust=False).mean()
    return atr

def compute_ema_trio(
    close: pd.Series, 
    fast: int = EMA_FAST, 
    mid: int = EMA_MID, 
    slow: int = EMA_SLOW
) -> Dict[str, pd.Series]:
    """
    Calculates Fast, Mid, and Slow EMAs.
    """
    return {
        "ema_fast": close.ewm(span=fast, adjust=False).mean(),
        "ema_mid": close.ewm(span=mid, adjust=False).mean(),
        "ema_slow": close.ewm(span=slow, adjust=False).mean(),
    }

def compute_volume_features(
    df: pd.DataFrame, 
    window: int = VOL_WINDOW, 
    spike_th: float = VOL_SPIKE_THRESHOLD, 
    dry_th: float = VOL_DRY_THRESHOLD
) -> Dict[str, pd.Series]:
    """
    Calculates volume features to detect sincerity of moves.
    """
    volume = df["volume"]
    vol_ma = volume.rolling(window=window, min_periods=1).mean()
    # Avoid division by zero
    vol_rel = volume / vol_ma.replace(0, 1) 
    
    vol_spike = (vol_rel >= spike_th).astype(int)
    vol_dry = (vol_rel <= dry_th).astype(int)
    
    return {
        "vol_ma": vol_ma,
        "vol_rel": vol_rel,
        "vol_spike": vol_spike,
        "vol_dry": vol_dry,
    }

def compute_rsi_ema(rsi: pd.Series, period: int = RSI_EMA_PERIOD) -> pd.Series:
    """
    Calculates EMA of the RSI itself.
    """
    return rsi.ewm(span=period, adjust=False).mean()


# --- Main Build Functions ---

def build_features_for_history_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enriches the history DataFrame with all indicators.
    """
    # Create a copy to avoid SettingWithCopy warnings on input df
    df = df.copy()
    
    # RSI
    rsi = compute_rsi(df["close"])
    rsi_ema = compute_rsi_ema(rsi)
    df["rsi"] = rsi
    df["rsi_ema"] = rsi_ema
    
    # MACD
    macd_dict = compute_macd(df["close"])
    df["macd_line"] = macd_dict["macd_line"]
    df["macd_signal"] = macd_dict["macd_signal"]
    df["macd_hist"] = macd_dict["macd_hist"]
    df["macd_phase"] = assign_macd_phase(df["macd_hist"])
    
    # ATR
    df["atr"] = compute_atr(df)
    
    # EMAs
    ema_trio = compute_ema_trio(df["close"])
    df["ema_fast"] = ema_trio["ema_fast"]
    df["ema_mid"] = ema_trio["ema_mid"]
    df["ema_slow"] = ema_trio["ema_slow"]
    
    # Volume
    vol_feats = compute_volume_features(df)
    df["vol_ma"] = vol_feats["vol_ma"]
    df["vol_rel"] = vol_feats["vol_rel"]
    df["vol_spike"] = vol_feats["vol_spike"]
    df["vol_dry"] = vol_feats["vol_dry"]
    
    # Optional: Drop initial rows where indicators are NaN (e.g. first 200 rows for EMA_SLOW)
    # For now, we keep them but user should be aware.
    # df.dropna(subset=["ema_slow"], inplace=True)
    
    return df

def build_features_for_symbol_timeframe(symbol: str, timeframe: str) -> pd.DataFrame:
    """
    Loads history, builds features, and saves to parquet.
    """
    history_file = coin_cell_paths.get_history_file(symbol, timeframe)
    
    if not history_file.exists():
        raise FileNotFoundError(f"History file not found for {symbol} {timeframe}. Run M2 update first.")
        
    df_history = pd.read_parquet(history_file)
    
    if df_history.empty:
        print(f"Warning: History is empty for {symbol} {timeframe}")
        return df_history
        
    df_features = build_features_for_history_df(df_history)
    
    # Save
    data_dir = coin_cell_paths.get_coin_data_dir(symbol)
    feature_file = data_dir / f"features_{timeframe}.parquet"
    
    df_features.to_parquet(feature_file, index=False)
    
    return df_features

def bulk_build_features(symbols: List[str], timeframes: List[str]) -> None:
    """
    Builds features for multiple coins and timeframes.
    """
    for symbol in symbols:
        for tf in timeframes:
            try:
                print(f"Building features for {symbol} {tf}...")
                build_features_for_symbol_timeframe(symbol, tf)
            except Exception as e:
                print(f"Failed to build features for {symbol} {tf}: {e}")
                continue
