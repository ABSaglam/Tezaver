"""
DSG Daily Indicator Deep Dive
==============================
Comprehensive analysis of technical indicators at the start of DSG rallies (1d timeframe only).
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

def calculate_rsi(series, period=14):
    """Calculate RSI."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, 0.001)
    return 100 - (100 / (1 + rs))

def calculate_ema(series, period):
    """Calculate EMA."""
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(close, fast=12, slow=26, signal=9):
    """Calculate MACD and MACD Histogram."""
    ema_fast = calculate_ema(close, fast)
    ema_slow = calculate_ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bollinger_bands(close, period=20, std_dev=2):
    """Calculate Bollinger Bands."""
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return upper, sma, lower

def classify_rsi(rsi):
    """Classify RSI into granular categories."""
    if pd.isna(rsi): return 'UNKNOWN'
    if rsi < 20: return 'EXTREME_OVERSOLD'
    if rsi < 30: return 'OVERSOLD'
    if rsi < 40: return 'WEAK'
    if rsi < 50: return 'NEUTRAL_LOW'
    if rsi < 60: return 'NEUTRAL_HIGH'
    if rsi < 70: return 'STRONG'
    if rsi < 80: return 'OVERBOUGHT'
    return 'EXTREME_OVERBOUGHT'

def classify_rsi_vs_ema(rsi, rsi_ema):
    """Classify RSI position relative to its EMA."""
    if pd.isna(rsi) or pd.isna(rsi_ema): return 'UNKNOWN'
    diff = rsi - rsi_ema
    if diff > 5: return 'ABOVE_EMA'
    if diff < -5: return 'BELOW_EMA'
    return 'AT_EMA'

def classify_macd(macd_line, signal_line):
    """Classify MACD position."""
    if pd.isna(macd_line) or pd.isna(signal_line): return 'UNKNOWN'
    if macd_line > signal_line and macd_line > 0: return 'BULLISH_POSITIVE'
    if macd_line > signal_line and macd_line < 0: return 'BULLISH_NEGATIVE'
    if macd_line < signal_line and macd_line > 0: return 'BEARISH_POSITIVE'
    if macd_line < signal_line and macd_line < 0: return 'BEARISH_NEGATIVE'
    return 'NEUTRAL'

def classify_macd_histogram(histogram):
    """Classify MACD Histogram."""
    if pd.isna(histogram): return 'UNKNOWN'
    if histogram > 0.5: return 'STRONG_BULLISH'
    if histogram > 0: return 'BULLISH'
    if histogram > -0.5: return 'BEARISH'
    return 'STRONG_BEARISH'

def classify_volume(volume, volume_ma):
    """Classify volume relative to moving average."""
    if pd.isna(volume) or pd.isna(volume_ma) or volume_ma == 0: return 'UNKNOWN'
    ratio = volume / volume_ma
    if ratio > 2.0: return 'EXTREME_HIGH'
    if ratio > 1.5: return 'HIGH'
    if ratio > 1.0: return 'ABOVE_AVG'
    if ratio > 0.7: return 'NORMAL'
    return 'LOW'

def classify_bb_position(close, upper, middle, lower):
    """Classify price position within Bollinger Bands."""
    if pd.isna(close) or pd.isna(upper) or pd.isna(lower): return 'UNKNOWN'
    
    band_width = upper - lower
    if band_width == 0: return 'FLAT'
    
    # Position as percentage within bands (0 = lower band, 100 = upper band)
    position = ((close - lower) / band_width) * 100
    
    if position > 100: return 'ABOVE_UPPER'
    if position > 80: return 'NEAR_UPPER'
    if position > 60: return 'UPPER_HALF'
    if position > 40: return 'MIDDLE'
    if position > 20: return 'LOWER_HALF'
    if position > 0: return 'NEAR_LOWER'
    return 'BELOW_LOWER'

def analyze_daily_indicators(symbol, start_time, tier):
    """Analyze all daily indicators at rally start time."""
    try:
        path = coin_cell_paths.get_history_file(symbol, '1d')
        if not path.exists():
            return None
        
        df = pd.read_parquet(path)
        df = df.sort_values('timestamp')
        
        # Find the bar at or just before start_time
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        df['ts_diff'] = (df['timestamp'] - start_ts).abs()
        idx = df['ts_diff'].idxmin()
        
        if idx < 30:  # Need enough history for indicators
            return None
        
        # Calculate all indicators
        df['rsi'] = calculate_rsi(df['close'], 14)
        df['rsi_ema'] = calculate_ema(df['rsi'], 9)
        
        macd_line, signal_line, histogram = calculate_macd(df['close'])
        df['macd'] = macd_line
        df['macd_signal'] = signal_line
        df['macd_hist'] = histogram
        
        df['volume_ma'] = df['volume'].rolling(20).mean()
        
        upper, middle, lower = calculate_bollinger_bands(df['close'], 20, 2)
        df['bb_upper'] = upper
        df['bb_middle'] = middle
        df['bb_lower'] = lower
        
        # Get values at specific index
        result = {
            'tier': tier,
            'rsi': df['rsi'].iloc[idx],
            'rsi_class': classify_rsi(df['rsi'].iloc[idx]),
            'rsi_ema': df['rsi_ema'].iloc[idx],
            'rsi_vs_ema': classify_rsi_vs_ema(df['rsi'].iloc[idx], df['rsi_ema'].iloc[idx]),
            'macd': df['macd'].iloc[idx],
            'macd_signal': df['macd_signal'].iloc[idx],
            'macd_class': classify_macd(df['macd'].iloc[idx], df['macd_signal'].iloc[idx]),
            'macd_hist': df['macd_hist'].iloc[idx],
            'macd_hist_class': classify_macd_histogram(df['macd_hist'].iloc[idx]),
            'volume': df['volume'].iloc[idx],
            'volume_ma': df['volume_ma'].iloc[idx],
            'volume_class': classify_volume(df['volume'].iloc[idx], df['volume_ma'].iloc[idx]),
            'bb_position': classify_bb_position(df['close'].iloc[idx], df['bb_upper'].iloc[idx], 
                                                df['bb_middle'].iloc[idx], df['bb_lower'].iloc[idx])
        }
        
        return result
        
    except Exception as e:
        return None

def run_analysis(tier='ALL'):
    print("=" * 80)
    print(f"📊 DAILY INDICATOR DEEP DIVE: {tier}")
    print(f"Started: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load rallies from DB
    conn = sqlite3.connect(DB_PATH)
    if tier == 'ALL':
        query = "SELECT * FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')"
    else:
        query = f"SELECT * FROM rallies WHERE tier = '{tier}'"
    
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    total = len(df_rallies)
    print(f"\nTotal Rallies: {total}\n")
    
    results = []
    
    for i, row in df_rallies.iterrows():
        if (i + 1) % 1000 == 0:
            print(f"Progress: {i+1}/{total} analyzed...")
        
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        symbol = raw_data['symbol']
        start_time = raw_data['start_time']
        
        analysis = analyze_daily_indicators(symbol, start_time, row['tier'])
        if analysis:
            results.append(analysis)
    
    if not results:
        print("\n❌ No valid data")
        return
    
    df = pd.DataFrame(results)
    
    # Generate detailed statistics
    print("\n" + "=" * 80)
    print("📈 DAILY INDICATOR STATISTICS")
    print("=" * 80)
    
    # Group by tier for comparison
    if tier == 'ALL':
        tiers = ['DIAMOND', 'GOLD', 'SILVER']
    else:
        tiers = [tier]
    
    for t in tiers:
        df_tier = df[df['tier'] == t]
        if df_tier.empty:
            continue
            
        print(f"\n{'─' * 80}")
        print(f"💎 {t} ({len(df_tier)} rallies)")
        print(f"{'─' * 80}")
        
        # RSI Distribution
        print(f"\n🔹 RSI LEVELS:")
        rsi_counts = df_tier['rsi_class'].value_counts().sort_index()
        for cls, count in rsi_counts.items():
            pct = (count / len(df_tier)) * 100
            avg_rsi = df_tier[df_tier['rsi_class'] == cls]['rsi'].mean()
            print(f"   {cls:20s}: {count:6d} ({pct:5.1f}%) | Avg RSI: {avg_rsi:5.1f}")
        
        # RSI vs EMA
        print(f"\n🔹 RSI vs RSI-EMA:")
        rsi_ema_counts = df_tier['rsi_vs_ema'].value_counts()
        for cls, count in rsi_ema_counts.items():
            pct = (count / len(df_tier)) * 100
            print(f"   {cls:20s}: {count:6d} ({pct:5.1f}%)")
        
        # MACD
        print(f"\n🔹 MACD POSITION:")
        macd_counts = df_tier['macd_class'].value_counts()
        for cls, count in macd_counts.items():
            pct = (count / len(df_tier)) * 100
            print(f"   {cls:20s}: {count:6d} ({pct:5.1f}%)")
        
        # MACD Histogram
        print(f"\n🔹 MACD HISTOGRAM:")
        hist_counts = df_tier['macd_hist_class'].value_counts()
        for cls, count in hist_counts.items():
            pct = (count / len(df_tier)) * 100
            print(f"   {cls:20s}: {count:6d} ({pct:5.1f}%)")
        
        # Volume
        print(f"\n🔹 VOLUME:")
        vol_counts = df_tier['volume_class'].value_counts()
        for cls, count in vol_counts.items():
            pct = (count / len(df_tier)) * 100
            print(f"   {cls:20s}: {count:6d} ({pct:5.1f}%)")
        
        # Bollinger Bands
        print(f"\n🔹 BOLLINGER BANDS POSITION:")
        bb_counts = df_tier['bb_position'].value_counts()
        for cls, count in bb_counts.items():
            pct = (count / len(df_tier)) * 100
            print(f"   {cls:20s}: {count:6d} ({pct:5.1f}%)")
    
    print("\n" + "=" * 80)
    print("✅ Analysis Complete")
    print("=" * 80)

if __name__ == "__main__":
    tier = sys.argv[1] if len(sys.argv) > 1 else 'ALL'
    tier = tier.upper()
    
    if tier not in ['DIAMOND', 'GOLD', 'SILVER', 'ALL']:
        print(f"Invalid tier: {tier}. Use DIAMOND, GOLD, SILVER, or ALL")
        sys.exit(1)
    
    run_analysis(tier)
