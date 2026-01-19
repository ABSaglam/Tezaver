"""
Multi-Indicator DSG Pattern Miner
=================================
Analyzes January 2026 DSG rallies with multiple indicators across timeframes.
Goal: Find patterns that distinguish successful vs failed signals.
"""

import sys
import os
import pandas as pd
import numpy as np
import json
import sqlite3
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

# === INDICATOR FUNCTIONS ===
def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def calculate_bb(prices, period=20, std_dev=2):
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    bb_position = (prices - lower) / (upper - lower)  # 0-1 range
    return upper, lower, bb_position

def add_indicators(df):
    """Add all indicators to a dataframe."""
    df = df.copy()
    df['rsi'] = calculate_rsi(df['close'])
    df['rsi_ema'] = df['rsi'].ewm(span=9).mean()
    df['rsi_above_ema'] = df['rsi'] > df['rsi_ema']
    
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df['ema_bullish'] = df['ema9'] > df['ema21']
    
    macd, signal, hist = calculate_macd(df['close'])
    df['macd'] = macd
    df['macd_signal'] = signal
    df['macd_hist'] = hist
    df['macd_bullish'] = macd > signal
    df['macd_hist_green'] = hist > 0
    df['macd_hist_rising'] = hist > hist.shift(1)
    
    bb_upper, bb_lower, bb_pos = calculate_bb(df['close'])
    df['bb_upper'] = bb_upper
    df['bb_lower'] = bb_lower
    df['bb_position'] = bb_pos
    df['bb_squeeze'] = (bb_upper - bb_lower) / df['close'] * 100 < 5  # Squeeze detection
    
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['week_change'] = df['close'].pct_change(7) * 100
    
    return df

def get_pre_rally_state(symbol, rally_time, timeframe):
    """Get indicator state before a rally."""
    path = coin_cell_paths.get_history_file(symbol, timeframe)
    if not path.exists():
        return None
    
    df = pd.read_parquet(path).sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = add_indicators(df)
    
    # Find the bar just before rally start
    rally_ts = pd.to_datetime(rally_time)
    pre_bars = df[df['datetime'] < rally_ts]
    
    if len(pre_bars) < 30:
        return None
    
    last = pre_bars.iloc[-1]
    
    return {
        'rsi': last['rsi'],
        'rsi_above_ema': last['rsi_above_ema'],
        'ema_bullish': last['ema_bullish'],
        'macd_bullish': last['macd_bullish'],
        'macd_hist_green': last['macd_hist_green'],
        'macd_hist_rising': last['macd_hist_rising'],
        'bb_position': last['bb_position'],
        'bb_squeeze': last['bb_squeeze'],
        'vol_ratio': last['vol_ratio'],
        'close_above_ema9': last['close'] > last['ema9']
    }

def analyze_dsg_patterns():
    print("=" * 70)
    print("🔬 MULTI-INDICATOR DSG PATTERN MINING (JANUARY 2026)")
    print("=" * 70)
    
    # Get all January DSG rallies
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, tier, event_time, raw_data FROM rallies 
        WHERE event_time >= '2026-01-01' AND event_time <= '2026-01-17' 
        AND tier IN ('DIAMOND', 'GOLD', 'SILVER')
    """)
    rallies = cursor.fetchall()
    conn.close()
    
    print(f"Total DSG Rallies in January: {len(rallies)}")
    
    results = []
    
    for i, (symbol, tier, event_time, raw_data) in enumerate(rallies[:100]):  # Sample first 100
        if i % 20 == 0:
            print(f"Processing {i}/{min(100, len(rallies))}...")
        
        raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        rally_time = raw['start_time']
        gain = raw.get('gain', 0)
        
        # Get states from multiple timeframes
        state_1d = get_pre_rally_state(symbol, rally_time, '1d')
        state_4h = get_pre_rally_state(symbol, rally_time, '4h')
        state_1w = get_pre_rally_state(symbol, rally_time, '1w')
        
        if not state_1d:
            continue
        
        result = {
            'symbol': symbol,
            'tier': tier,
            'gain': gain,
            # Daily
            'd_rsi': state_1d['rsi'],
            'd_rsi_above_ema': state_1d['rsi_above_ema'],
            'd_ema_bullish': state_1d['ema_bullish'],
            'd_macd_bullish': state_1d['macd_bullish'],
            'd_macd_green': state_1d['macd_hist_green'],
            'd_macd_rising': state_1d['macd_hist_rising'],
            'd_bb_pos': state_1d['bb_position'],
            'd_bb_squeeze': state_1d['bb_squeeze'],
            'd_close_above_ema': state_1d['close_above_ema9'],
            'd_vol_ratio': state_1d['vol_ratio'],
        }
        
        # 4H
        if state_4h:
            result['h4_macd_bullish'] = state_4h['macd_bullish']
            result['h4_macd_green'] = state_4h['macd_hist_green']
            result['h4_rsi_above_ema'] = state_4h['rsi_above_ema']
            result['h4_close_above_ema'] = state_4h['close_above_ema9']
        
        # Weekly
        if state_1w:
            result['w_macd_bullish'] = state_1w['macd_bullish']
            result['w_macd_green'] = state_1w['macd_hist_green']
            result['w_rsi_above_ema'] = state_1w['rsi_above_ema']
        
        results.append(result)
    
    df = pd.DataFrame(results)
    
    # Analyze patterns
    print("\n" + "=" * 70)
    print("📊 INDICATOR PATTERN ANALYSIS")
    print("=" * 70)
    
    # Boolean columns to analyze
    bool_cols = [c for c in df.columns if df[c].dtype == bool or c.endswith('_bullish') or c.endswith('_green') or c.endswith('_rising') or c.endswith('_ema')]
    
    print("\n--- SINGLE INDICATOR HIT RATES ---")
    for col in bool_cols:
        if col in df.columns:
            true_count = df[col].sum()
            true_pct = true_count / len(df) * 100
            print(f"{col:25}: {true_count:3}/{len(df)} ({true_pct:5.1f}%)")
    
    # Find best combinations
    print("\n--- BEST COMBINATIONS (All DSG Rallies) ---")
    combos = [
        ('d_macd_bullish', 'd_rsi_above_ema'),
        ('d_macd_green', 'd_close_above_ema'),
        ('d_macd_rising', 'd_ema_bullish'),
        ('d_macd_green', 'h4_macd_green'),
        ('d_close_above_ema', 'h4_close_above_ema'),
        ('w_macd_bullish', 'd_macd_bullish'),
        ('w_macd_green', 'd_macd_green'),
        ('d_rsi_above_ema', 'h4_rsi_above_ema'),
    ]
    
    for c1, c2 in combos:
        if c1 in df.columns and c2 in df.columns:
            match = df[(df[c1] == True) & (df[c2] == True)]
            pct = len(match) / len(df) * 100
            print(f"{c1} + {c2}: {len(match)}/{len(df)} ({pct:.1f}%)")
    
    # Diamond-specific patterns
    print("\n--- DIAMOND SPECIFIC PATTERNS ---")
    diamonds = df[df['tier'] == 'DIAMOND']
    print(f"Diamond count: {len(diamonds)}")
    
    for col in bool_cols:
        if col in diamonds.columns:
            true_count = diamonds[col].sum()
            if len(diamonds) > 0:
                true_pct = true_count / len(diamonds) * 100
                print(f"{col:25}: {true_count:3}/{len(diamonds)} ({true_pct:5.1f}%)")
    
    return df

if __name__ == "__main__":
    df = analyze_dsg_patterns()
    
    # Save for further analysis
    output_path = coin_cell_paths.get_library_root() / "dsg_pattern_analysis.csv"
    df.to_csv(output_path, index=False)
    print(f"\nSaved to: {output_path}")
