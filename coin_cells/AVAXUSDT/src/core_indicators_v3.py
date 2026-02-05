import pandas as pd
import numpy as np

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0)
    avg_gain = gain.rolling(window=period, min_periods=1).mean()
    avg_loss = loss.rolling(window=period, min_periods=1).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_extended_indicators(df):
    """
    Calculates internal V3 indicators (Ribbon, RSI-EMA) and adds State Flags.
    These flags are internal and NOT part of V17 schema export.
    """
    df = df.copy()
    close = df['close']
    
    # 1. RSI (14)
    df['RSI'] = calculate_rsi(close, 14)
    
    # 2. RSI-EMA (9)
    df['RSI_EMA'] = df['RSI'].ewm(span=9, adjust=False).mean()
    
    # RSI Slope (Simple diff)
    df['RSI_EMA_Slope'] = df['RSI_EMA'].diff()
    
    # 3. EMA Ribbon [8, 13, 21, 34, 55]
    emas = {}
    periods = [8, 13, 21, 34, 55]
    for p in periods:
        emas[p] = close.ewm(span=p, adjust=False).mean()
        
    # Upper/Lower Ribbon
    # We can perform row-wise max/min efficiently
    ema_df = pd.DataFrame(emas)
    df['Ribbon_Upper'] = ema_df.max(axis=1)
    df['Ribbon_Lower'] = ema_df.min(axis=1)
    df['Ribbon_Width_Pct'] = (df['Ribbon_Upper'] - df['Ribbon_Lower']) / close
    
    # 21 EMA Slope for trend context
    df['EMA21_Slope'] = emas[21].diff()

    # 4. STATE GENERATION
    # RIBBON_INSIDE
    df['STATE_RIBBON_INSIDE'] = (close >= df['Ribbon_Lower']) & (close <= df['Ribbon_Upper'])
    
    # RIBBON_BREAK_UP
    df['STATE_RIBBON_BREAK_UP'] = (close > df['Ribbon_Upper']) & (df['EMA21_Slope'] >= 0)
    
    # RIBBON_BREAK_DN
    df['STATE_RIBBON_BREAK_DN'] = (close < df['Ribbon_Lower']) & (df['EMA21_Slope'] <= 0)
    
    # RIBBON_SUPPRESSION_UP
    # Inside + close near upper (e.g. upper half of ribbon) + RSI < RSI-EMA
    # Simplified: Inside + RSI < RSI_EMA is suppression if trend is attempting up
    df['STATE_RIBBON_SUPPRESSION_UP'] = (df['STATE_RIBBON_INSIDE']) & (df['RSI'] < df['RSI_EMA'])
    
    # RSI_LOCK_UP
    df['STATE_RSI_LOCK_UP'] = (df['RSI'] > df['RSI_EMA']) & (df['RSI_EMA_Slope'] > 0)
    
    # RSI_LOCK_DN
    df['STATE_RSI_LOCK_DN'] = (df['RSI'] < df['RSI_EMA']) & (df['RSI_EMA_Slope'] < 0)
    
    return df
