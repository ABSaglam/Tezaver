"""
DSG Rally Trend DNA Analyzer
=============================
Analyzes the multi-timeframe trend characteristics that precede DSG tier rallies.
Usage: python analyze_diamond_dna.py [DIAMOND|GOLD|SILVER]
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def calculate_ema(series, period=20):
    """Calculate Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()

def calculate_rsi(series, period=14):
    """Calculate RSI."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def calculate_atr_pct(df, period=14):
    """Calculate ATR%."""
    high_low = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift(1)).abs()
    low_close = (df['low'] - df['close'].shift(1)).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    return (atr / df['close']) * 100

def classify_trend(df, idx):
    """Classify trend direction at given index."""
    if idx < 20:
        return 'INSUFFICIENT_DATA'
    
    close = df['close'].iloc[idx]
    ema20 = calculate_ema(df['close'][:idx+1], 20).iloc[-1]
    
    if close > ema20 * 1.02:
        return 'UPTREND'
    elif close < ema20 * 0.98:
        return 'DOWNTREND'
    else:
        return 'SIDEWAYS'

def classify_rsi(rsi_value):
    """Classify RSI level."""
    if pd.isna(rsi_value):
        return 'UNKNOWN'
    if rsi_value < 30:
        return 'OVERSOLD'
    elif rsi_value > 70:
        return 'OVERBOUGHT'
    else:
        return 'NEUTRAL'

def classify_atr(atr_value):
    """Classify ATR% level."""
    if pd.isna(atr_value):
        return 'UNKNOWN'
    if atr_value < 5:
        return 'LOW'
    elif atr_value < 15:
        return 'MEDIUM'
    else:
        return 'HIGH'

def classify_price_position(df, idx):
    """Classify price position within recent range."""
    if idx < 20:
        return 'INSUFFICIENT_DATA'
    
    window = df.iloc[max(0, idx-20):idx+1]
    high_20 = window['high'].max()
    low_20 = window['low'].min()
    current_close = df['close'].iloc[idx]
    
    range_size = high_20 - low_20
    if range_size == 0:
        return 'FLAT'
    
    position = (current_close - low_20) / range_size
    
    if position < 0.25:
        return 'BOTTOM_QUARTER'
    elif position > 0.75:
        return 'TOP_QUARTER'
    else:
        return 'MIDDLE'

def analyze_diamond_at_timeframe(symbol, start_time, timeframe):
    """Analyze trend characteristics at a specific timeframe."""
    try:
        path = coin_cell_paths.get_history_file(symbol, timeframe)
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        df = df.sort_values('timestamp')
        
        # Find the bar at or just before start_time
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        df['ts_diff'] = (df['timestamp'] - start_ts).abs()
        idx = df['ts_diff'].idxmin()
        
        if idx < 20:
            return None
        
        # Calculate indicators
        df['ema20'] = calculate_ema(df['close'], 20)
        df['rsi'] = calculate_rsi(df['close'], 14)
        df['atr_pct'] = calculate_atr_pct(df, 14)
        
        # Get values at the specific index
        trend = classify_trend(df, idx)
        rsi_class = classify_rsi(df['rsi'].iloc[idx])
        atr_class = classify_atr(df['atr_pct'].iloc[idx])
        price_pos = classify_price_position(df, idx)
        
        return {
            'trend': trend,
            'rsi_class': rsi_class,
            'rsi_value': df['rsi'].iloc[idx],
            'atr_class': atr_class,
            'atr_value': df['atr_pct'].iloc[idx],
            'price_position': price_pos
        }
        
    except Exception as e:
        return None

def run_analysis(tier='DIAMOND'):
    print("=" * 70)
    print(f"💎 {tier} RALLY TREND DNA ANALYSIS")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 70)
    
    # Load rallies from DB
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT * FROM rallies WHERE tier = '{tier}'"
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    total = len(df_rallies)
    print(f"\nTotal Diamond Rallies: {total}")
    print("\nAnalyzing multi-timeframe conditions...\n")
    
    results = {
        '1w': [],
        '1d': [],
        '4h': []
    }
    
    for i, row in df_rallies.iterrows():
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        symbol = raw_data['symbol']
        start_time = raw_data['start_time']
        
        if (i + 1) % 100 == 0:
            print(f"Progress: {i+1}/{total} rallies analyzed...")
        
        # Analyze each timeframe
        for tf in ['1w', '1d', '4h']:
            analysis = analyze_diamond_at_timeframe(symbol, start_time, tf)
            if analysis:
                results[tf].append(analysis)
    
    # Generate Statistics
    print("\n" + "=" * 70)
    print("📊 STATISTICAL RESULTS")
    print("=" * 70)
    
    for tf in ['1w', '1d', '4h']:
        print(f"\n{'─' * 70}")
        print(f"⏱️  {tf.upper()} TIMEFRAME ANALYSIS")
        print(f"{'─' * 70}")
        
        if not results[tf]:
            print("❌ Insufficient data\n")
            continue
        
        df_tf = pd.DataFrame(results[tf])
        total_valid = len(df_tf)
        
        # Trend Distribution
        print(f"\n🔹 TREND DIRECTION (n={total_valid}):")
        trend_counts = df_tf['trend'].value_counts()
        for trend, count in trend_counts.items():
            pct = (count / total_valid) * 100
            print(f"   {trend:20s}: {count:5d} ({pct:5.1f}%)")
        
        # RSI Distribution
        print(f"\n🔹 RSI LEVELS (n={total_valid}):")
        rsi_counts = df_tf['rsi_class'].value_counts()
        for rsi_class, count in rsi_counts.items():
            pct = (count / total_valid) * 100
            print(f"   {rsi_class:20s}: {count:5d} ({pct:5.1f}%)")
        avg_rsi = df_tf['rsi_value'].mean()
        print(f"   {'Average RSI':20s}: {avg_rsi:5.1f}")
        
        # ATR Distribution
        print(f"\n🔹 VOLATILITY (ATR%) (n={total_valid}):")
        atr_counts = df_tf['atr_class'].value_counts()
        for atr_class, count in atr_counts.items():
            pct = (count / total_valid) * 100
            print(f"   {atr_class:20s}: {count:5d} ({pct:5.1f}%)")
        avg_atr = df_tf['atr_value'].mean()
        print(f"   {'Average ATR%':20s}: {avg_atr:5.1f}%")
        
        # Price Position Distribution
        print(f"\n🔹 PRICE POSITION (n={total_valid}):")
        pos_counts = df_tf['price_position'].value_counts()
        for pos, count in pos_counts.items():
            pct = (count / total_valid) * 100
            print(f"   {pos:20s}: {count:5d} ({pct:5.1f}%)")
    
    print("\n" + "=" * 70)
    print("✅ Analysis Complete")
    print("=" * 70)

if __name__ == "__main__":
    tier = sys.argv[1] if len(sys.argv) > 1 else 'DIAMOND'
    tier = tier.upper()
    
    if tier not in ['DIAMOND', 'GOLD', 'SILVER']:
        print(f"Invalid tier: {tier}. Use DIAMOND, GOLD, or SILVER")
        sys.exit(1)
    
    run_analysis(tier)
