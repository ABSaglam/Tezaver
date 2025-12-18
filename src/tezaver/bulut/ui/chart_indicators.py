# Tezaver Bulut - Charting Indicators
"""
Pure Pandas implementations of technical indicators for UI.
Avoids heavy dependencies like TA-Lib.
"""

import pandas as pd
import numpy as np

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    RSI with Wilder's Smoothing.
    """
    delta = series.diff()
    
    # Separate gains and losses
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    # Wilder's Smoothing (alpha = 1/period)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero (if avg_loss is 0, RSI is 100)
    rsi = rsi.fillna(50) # Neutral fill for start
    # Better: if avg_loss is 0, RSI is 100. If both 0, RSI 50.
    # But pandas handles inf usually.
    return rsi

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """
    MACD (Fast EMA - Slow EMA) and Signal Line.
    Returns: macd_line, signal_line, histogram
    """
    ema_fast = calculate_ema(series, fast)
    ema_slow = calculate_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Average True Range (Wilder's Smoothing).
    """
    # TR = Max(H-L, |H-Cp|, |L-Cp|)
    prev_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # ATR is EMA/Wilder of TR
    atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    return atr
