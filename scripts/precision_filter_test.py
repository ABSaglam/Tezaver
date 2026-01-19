"""
Multi-Timeframe High-Precision Filter
======================================
Goal: 100% hit rate in January 2026
- Combine Diamond+Gold data
- Trend confirmation: Daily + Weekly + 4H
- Strict filters
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import timedelta
import sqlite3
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_trend(df, idx):
    """Check if coin is in uptrend at given index."""
    if idx < 50:
        return False
    
    close = df.loc[idx, 'close']
    ema9 = df.loc[idx, 'ema9']
    ema20 = df.loc[idx, 'ema20']
    ema50 = df.loc[idx, 'ema50']
    
    # Full trend alignment
    if close > ema9 > ema20 > ema50:
        return True
    # Partial alignment
    if close > ema20 and ema9 > ema20:
        return True
    return False

def get_multi_tf_conditions(symbol, check_date):
    """Get conditions from multiple timeframes."""
    
    result = {
        'daily_trend': False,
        'weekly_trend': False,
        '4h_trend': False,
        'daily_rsi': 50,
        'daily_atr': 0,
        'daily_vol_ratio': 1,
        'valid': False
    }
    
    try:
        # Daily
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if path_1d.exists():
            df_1d = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
            df_1d['date'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
            df_1d['rsi'] = calculate_rsi(df_1d['close'])
            df_1d['ema9'] = df_1d['close'].ewm(span=9).mean()
            df_1d['ema20'] = df_1d['close'].ewm(span=20).mean()
            df_1d['ema50'] = df_1d['close'].ewm(span=50).mean()
            df_1d['atr'] = (df_1d['high'] - df_1d['low']) / df_1d['close'] * 100
            df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
            df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
            
            # Find the row for check_date (previous day's close)
            check_ts = pd.Timestamp(check_date) - timedelta(days=1)
            mask = df_1d['date'].dt.date == check_ts.date()
            if mask.any():
                idx = df_1d[mask].index[0]
                result['daily_trend'] = check_trend(df_1d, idx)
                result['daily_rsi'] = df_1d.loc[idx, 'rsi']
                result['daily_atr'] = df_1d.loc[idx, 'atr']
                result['daily_vol_ratio'] = df_1d.loc[idx, 'vol_ratio']
                result['valid'] = True
        
        # 4H
        path_4h = coin_cell_paths.get_history_file(symbol, '4h')
        if path_4h.exists():
            df_4h = pd.read_parquet(path_4h).sort_values('timestamp').reset_index(drop=True)
            df_4h['date'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
            df_4h['ema9'] = df_4h['close'].ewm(span=9).mean()
            df_4h['ema20'] = df_4h['close'].ewm(span=20).mean()
            df_4h['ema50'] = df_4h['close'].ewm(span=50).mean()
            
            check_ts = pd.Timestamp(check_date) - timedelta(hours=4)
            mask = df_4h['date'] <= check_ts
            if mask.any():
                idx = df_4h[mask].index[-1]
                result['4h_trend'] = check_trend(df_4h, idx)
        
        # Weekly (use daily data, check 5-day trend)
        if path_1d.exists():
            mask = df_1d['date'].dt.date <= (pd.Timestamp(check_date) - timedelta(days=1)).date()
            if mask.any():
                last_5 = df_1d[mask].tail(5)
                if len(last_5) >= 5:
                    # Upward trend in last 5 days
                    result['weekly_trend'] = last_5['close'].iloc[-1] > last_5['close'].iloc[0]
        
    except Exception as e:
        pass
    
    return result

def run_precision_test():
    print("=" * 80)
    print("🎯 YÜKSEK HASSASIYETLI FİLTRE TESTİ")
    print("=" * 80)
    
    # Test dates in January 2026
    test_dates = pd.date_range('2026-01-01', '2026-01-17', freq='D')
    
    all_signals = []
    
    for test_date in test_dates:
        for symbol in DEFAULT_COINS:
            conditions = get_multi_tf_conditions(symbol, test_date)
            
            if not conditions['valid']:
                continue
            
            # STRICT FILTERS
            # 1. All timeframes must show uptrend
            if not (conditions['daily_trend'] and conditions['4h_trend'] and conditions['weekly_trend']):
                continue
            
            # 2. RSI momentum (40-70 range)
            if not (40 <= conditions['daily_rsi'] <= 70):
                continue
            
            # 3. High ATR (volatility)
            if conditions['daily_atr'] < 10:
                continue
            
            # 4. Volume confirmation
            if conditions['daily_vol_ratio'] < 1.0:
                continue
            
            # Calculate next day result
            path_1d = coin_cell_paths.get_history_file(symbol, '1d')
            if not path_1d.exists():
                continue
            
            df = pd.read_parquet(path_1d).sort_values('timestamp')
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # Get signal day and result day
            signal_mask = df['date'].dt.date == (test_date - timedelta(days=1)).date()
            result_mask = df['date'].dt.date == test_date.date()
            
            if not signal_mask.any() or not result_mask.any():
                continue
            
            signal_row = df[signal_mask].iloc[0]
            result_row = df[result_mask].iloc[0]
            
            entry = signal_row['close']
            max_gain = (result_row['high'] - entry) / entry * 100
            close_gain = (result_row['close'] - entry) / entry * 100
            
            all_signals.append({
                'symbol': symbol,
                'signal_date': test_date - timedelta(days=1),
                'result_date': test_date,
                'daily_trend': conditions['daily_trend'],
                '4h_trend': conditions['4h_trend'],
                'weekly_trend': conditions['weekly_trend'],
                'rsi': conditions['daily_rsi'],
                'atr': conditions['daily_atr'],
                'vol_ratio': conditions['daily_vol_ratio'],
                'max_gain': max_gain,
                'close_gain': close_gain
            })
    
    df = pd.DataFrame(all_signals)
    
    if len(df) > 0:
        print(f"\nToplam Sinyal: {len(df)}")
        print(f"\n📊 SONUÇLAR:")
        print(f"Ortalama Max Kazanç: {df['max_gain'].mean():.1f}%")
        print(f"Medyan Max: {df['max_gain'].median():.1f}%")
        print(f"Min Max Kazanç: {df['max_gain'].min():.1f}%")
        print(f"Ortalama Kapanış: {df['close_gain'].mean():.1f}%")
        
        # Success tiers
        hit_10 = len(df[df['max_gain'] >= 10])
        hit_5 = len(df[df['max_gain'] >= 5])
        positive = len(df[df['max_gain'] > 0])
        
        print(f"\n>10% max: {hit_10}/{len(df)} ({hit_10/len(df)*100:.1f}%)")
        print(f">5% max: {hit_5}/{len(df)} ({hit_5/len(df)*100:.1f}%)")
        print(f">0% max: {positive}/{len(df)} ({positive/len(df)*100:.1f}%)")
        
        print("\n📋 TÜM SİNYALLER:")
        df = df.sort_values('result_date')
        for _, row in df.iterrows():
            status = "✅" if row['max_gain'] >= 10 else ("🟡" if row['max_gain'] >= 5 else "❌")
            print(f"{row['result_date'].strftime('%m-%d')} {row['symbol']:15s} RSI:{row['rsi']:.0f} ATR:{row['atr']:.1f}% Vol:{row['vol_ratio']:.1f}x → Max:{row['max_gain']:+.1f}% {status}")
    else:
        print("Sinyal bulunamadı - filtreler çok sıkı")

if __name__ == "__main__":
    run_precision_test()
