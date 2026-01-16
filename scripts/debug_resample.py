#!/usr/bin/env python3
import pandas as pd
from tezaver.core import coin_cell_paths

path = coin_cell_paths.get_history_file('A2ZUSDT', '15m')
if path.exists():
    df_15m = pd.read_parquet(path)
    print(f"Original 15m rows: {len(df_15m)}")
    print(df_15m.head())

    df = df_15m.resample('1D', on='datetime').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }).dropna()
    
    print("\nResampled 1D rows: ", len(df))
    print(df.tail(10))
    
    # Check signal logic
    df['atr_val'] = (df['high'] - df['low']).rolling(14).mean()
    df['atr_pct'] = (df['atr_val'] / df['close']) * 100
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, 0.001)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    print("\nSample Indicators:")
    print(df[['close', 'atr_pct', 'rsi']].tail(10))
    
    # Check Criteria
    mask = (
        ((df['atr_pct'] > 15) & (df['rsi'] > 55) & (df['rsi'] < 70)) | # TREND
        ((df['atr_pct'] > 12) & (df['atr_pct'] <= 15) & (df['rsi'] > 60) & (df['rsi'] < 75)) # NINJA
    )
    sig_dates = df[mask].index.tolist()
    print("\nSignals found:", len(sig_dates))
    print(sig_dates)
else:
    print("Path not found")
