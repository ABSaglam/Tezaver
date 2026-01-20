"""
C98USDT Deep 4H Analysis
========================
Testing 4H Candlestick Patterns + Momentum Strategies.
Logic: If ANY 4H candle on Day T meets criteria -> Predict Rally on Day T+1.
"""

import sys
import os
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def detect_4h_patterns(df):
    """Detect candlestick patterns on 4H data"""
    df['body'] = abs(df['close'] - df['open'])
    df['upper_shadow'] = df['high'] - df[['close', 'open']].max(axis=1)
    df['lower_shadow'] = df[['close', 'open']].min(axis=1) - df['low']
    df['total_range'] = df['high'] - df['low']
    # Avoid division by zero
    df['body_pct'] = (df['body'] / df['total_range'].replace(0, 0.0001)) * 100
    
    df['is_bullish'] = df['close'] > df['open']
    
    # Doji
    df['doji'] = df['body_pct'] < 5
    
    # Hammer
    df['hammer'] = (
        (df['lower_shadow'] > df['body'] * 2) &
        (df['upper_shadow'] < df['body'] * 0.3) &
        (df['body_pct'] < 30)
    )
    
    # Shooting Star
    df['shooting_star'] = (
        (df['upper_shadow'] > df['body'] * 2) &
        (df['lower_shadow'] < df['body'] * 0.3) &
        (df['body_pct'] < 30)
    )
    
    # Bullish Engulfing
    df['bullish_engulfing'] = (
        df['is_bullish'] &
        (df['is_bullish'].shift(1) == False) &
        (df['open'] < df['close'].shift(1)) &
        (df['close'] > df['open'].shift(1))
    )
    
    # Bearish Engulfing
    df['bearish_engulfing'] = (
        (df['is_bullish'] == False) &
        (df['is_bullish'].shift(1) == True) &
        (df['open'] > df['close'].shift(1)) &
        (df['close'] < df['open'].shift(1))
    )
    
    # Marubozu (Strong Momentum)
    df['bullish_marubozu'] = (df['is_bullish']) & (df['body_pct'] > 85)
    df['bearish_marubozu'] = (~df['is_bullish']) & (df['body_pct'] > 85)

    return df

def main():
    symbol = 'C98USDT'
    print(f"🔬 {symbol} - DEEP 4H ANALYSIS")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    # Load 4H Data
    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h'))
    df_4h = df_4h.sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h = df_4h[df_4h['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    df_4h['date'] = df_4h['datetime'].dt.date
    
    # Indicators
    df_4h['mom_1c'] = (df_4h['close'] / df_4h['close'].shift(1) - 1) * 100 # 4h momentum
    df_4h['mom_6c'] = (df_4h['close'] / df_4h['close'].shift(6) - 1) * 100 # 24h momentum rolling
    
    # Detect Patterns
    df_4h = detect_4h_patterns(df_4h)
    
    # Get List of Days to iterate (from 1D file logic usually, but here we scan unique dates in 4H)
    unique_dates = sorted(df_4h['date'].unique())
    # Skip first few days for indicators stability
    scan_dates = unique_dates[5:-1]
    
    print("\n🔍 Scanning 4H Strategies (Aggregated by Day)...")
    print("-" * 70)
    
    best_results = []
    
    patterns = ['doji', 'hammer', 'shooting_star', 'bullish_engulfing', 'bearish_engulfing', 'bullish_marubozu', 'bearish_marubozu']
    modifiers = [
        ('ANY', lambda x: x.any()), # Any candle in the day matches
        ('LAST', lambda x: x.iloc[-1] if len(x)>0 else False) # Last candle of the day matches
    ]
    
    # 1. Simple Pattern Check
    for pat in patterns:
        for mod_name, mod_func in modifiers:
            signals = []
            
            for d in scan_dates:
                # Get all 4h candles for this day
                day_candles = df_4h[df_4h['date'] == d]
                if len(day_candles) == 0: continue
                
                # Check condition
                matches = day_candles[pat]
                is_signal = mod_func(matches)
                
                if is_signal:
                    # Check Next Day Rally
                    # Note: We need to find T+1. Since unique_dates is sorted, we can look up or calculate.
                    # Simplest is date logic:
                    next_day = d + pd.Timedelta(days=1)
                    is_rally = next_day in rally_results
                    signals.append(is_rally)
            
            if len(signals) >= 5:
                hits = sum(signals)
                total = len(signals)
                prec = hits / total * 100
                if prec >= 40: # Print only interesting ones
                     print(f"  {mod_name} 4H {pat}: {total} signals, {hits} hits -> {prec:.1f}%")
                     if prec > 90: best_results.append((prec, f"{mod_name} 4H {pat}"))

    # 2. Pattern + Momentum Check
    print("\n🔍 4H Pattern + Momentum > X%...")
    for pat in patterns:
        for mom_thresh in [3, 5]:
            # Rule: Any 4h candle has (Pattern AND mom_1c >= thresh)
            signals = []
            for d in scan_dates:
                day_candles = df_4h[df_4h['date'] == d]
                if len(day_candles) == 0: continue
                
                condition = (day_candles[pat]) & (day_candles['mom_1c'] >= mom_thresh)
                if condition.any(): # Using ANY for this combo
                    next_day = d + pd.Timedelta(days=1)
                    is_rally = next_day in rally_results
                    signals.append(is_rally)
                    
            if len(signals) >= 5:
                hits = sum(signals)
                total = len(signals)
                prec = hits / total * 100
                if prec >= 50:
                    print(f"  ANY 4H ({pat} & mom_4h>={mom_thresh}%): {total} signals -> {prec:.1f}%")

    # 3. Pure High Momentum on 4H
    print("\n🔍 Pure High 4H Momentum...")
    for mom_thresh in [5, 8, 10, 15, 20]:
         signals = []
         for d in scan_dates:
            day_candles = df_4h[df_4h['date'] == d]
            if len(day_candles) == 0: continue
            
            # If ANY candle has mom >= thresh
            if (day_candles['mom_1c'] >= mom_thresh).any():
                next_day = d + pd.Timedelta(days=1)
                is_rally = next_day in rally_results
                signals.append(is_rally)
                
         if len(signals) >= 5:
            hits = sum(signals)
            total = len(signals)
            prec = hits / total * 100
            if prec >= 50:
                print(f"  ANY 4H mom>={mom_thresh}%: {total} signals -> {prec:.1f}%")
    
    print("\n✅ 4H Sweep Complete")

if __name__ == "__main__":
    main()
