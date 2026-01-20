#!/usr/bin/env python3
"""
🔍 DEBUG: RALLİ ASM 15M — State Transition Logger
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".")))

def calc_indicators(df):
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    
    df['tr'] = np.maximum(
        df['high'] - df['low'],
        np.maximum(
            abs(df['high'] - df['close'].shift(1)),
            abs(df['low'] - df['close'].shift(1))
        )
    )
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_ma'] = df['atr'].rolling(50).mean()
    
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    df['vol_ma'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma']
    
    df['is_green'] = df['close'] > df['open']
    
    return df

def main():
    symbol = 'ALGOUSDT'
    test_date = '2024-12-02'
    
    print(f"🔍 DEBUG: RALLİ ASM 15M — STATE INSPECTOR")
    print(f"Test Date: {test_date}")
    print("="*70)
    
    # Load data
    path = f"coin_cells/{symbol}/data/history_15m.parquet"
    df = pd.read_parquet(path)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df.sort_values('datetime').reset_index(drop=True)
    
    # Filter for test day
    start = pd.Timestamp(test_date)
    end = pd.Timestamp(test_date) + timedelta(days=1)
    mask = (df['datetime'] >= start) & (df['datetime'] < end)
    test_df = df[mask].reset_index(drop=True)
    test_df = calc_indicators(test_df)
    
    print(f"Candles on {test_date}: {len(test_df)}")
    
    # Check key conditions
    print("\n📊 KEY INDICATOR RANGES ON THIS DAY:")
    print(f"  RSI Range: {test_df['rsi'].min():.1f} - {test_df['rsi'].max():.1f}")
    print(f"  ATR/ATR_MA Ratio: {(test_df['atr'] / test_df['atr_ma']).mean():.2f}")
    print(f"  Volume Ratio Range: {test_df['vol_ratio'].min():.2f} - {test_df['vol_ratio'].max():.2f}")
    print(f"  Green Candle %: {test_df['is_green'].mean()*100:.1f}%")
    
    # Check EMA alignment
    ema_aligned = test_df['ema9'] > test_df['ema21']
    full_aligned = (test_df['ema9'] > test_df['ema21']) & (test_df['ema21'] > test_df['ema50'])
    print(f"  EMA9 > EMA21: {ema_aligned.mean()*100:.1f}% of candles")
    print(f"  Full EMA Alignment (9>21>50): {full_aligned.mean()*100:.1f}% of candles")
    
    # Check SQUEEZED condition
    squeezed = test_df['atr'] < test_df['atr_ma'] * 0.7
    print(f"  SQUEEZED (ATR < 0.7×ATR_MA): {squeezed.mean()*100:.1f}% of candles")
    
    # Check COMMITTED conditions individually
    print("\n🔑 COMMITTED CONDITIONS CHECK:")
    for i in range(50, len(test_df)):
        row = test_df.iloc[i]
        
        ema_ok = row['ema9'] > row['ema21'] > row['ema50']
        atr_ok = row['atr'] > row['atr_ma'] * 0.9 if not pd.isna(row['atr_ma']) else False
        rsi_ok = 55 < row['rsi'] < 75
        vol_ok = row['vol_ratio'] > 1.5
        
        last_8 = test_df.iloc[max(0,i-7):i+1]
        green_count = last_8['is_green'].sum()
        struct_ok = green_count >= 5
        
        above_anchor = row['close'] > row['ema50']
        
        all_ok = all([ema_ok, atr_ok, rsi_ok, vol_ok, struct_ok, above_anchor])
        
        if all_ok:
            print(f"  ✅ {row['datetime']} -> ALL CONDITIONS MET!")
        elif i < 55:  # Only print first few
            fails = []
            if not ema_ok: fails.append("EMA")
            if not atr_ok: fails.append("ATR")
            if not rsi_ok: fails.append(f"RSI({row['rsi']:.0f})")
            if not vol_ok: fails.append(f"VOL({row['vol_ratio']:.1f})")
            if not struct_ok: fails.append(f"STRUCT({green_count}/8)")
            if not above_anchor: fails.append("ANCHOR")
            print(f"  ❌ {row['datetime']} | Fails: {', '.join(fails)}")

if __name__ == "__main__":
    main()
