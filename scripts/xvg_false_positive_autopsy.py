"""
XVGUSDT False Positive Autopsy
===============================
Analyzes why signals FAILED to produce DG rallies.
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

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

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

def get_macd_color(hist_current, hist_prev):
    if hist_current > 0:
        return 'GREEN_RISING 🟢↗' if hist_current > hist_prev else 'GREEN_FALLING 🟢↘'
    else:
        return 'RED_RISING 🔴↗' if hist_current > hist_prev else 'RED_FALLING 🔴↘'

def detector_b_momentum(df_1d, idx):
    """Detector B: Momentum Surfer"""
    sig = df_1d.loc[idx]
    
    if sig['rsi'] < 75:
        return False
    if sig['macd_hist'] <= 0:
        return False
    if not sig['macd_rising']:
        return False
    
    body = abs(sig['close'] - sig['open']) / sig['open'] * 100
    if body < 15:
        return False
    if sig['close'] <= sig['ema9']:
        return False
    
    return True

def analyze_false_positives():
    print("="*100)
    print("🔬 XVGUSDT - FALSE POSITIVE AUTOPSY")
    print("="*100)
    
    # Get ground truth
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_time, raw_data, tier FROM rallies 
        WHERE symbol = 'XVGUSDT' AND tier IN ('DIAMOND', 'GOLD', 'SILVER', 'BRONZE', 'IRON')
        ORDER BY event_time
    """)
    all_rallies = cursor.fetchall()
    conn.close()
    
    # Map dates to tiers
    rally_map = {}
    dg_dates = set()
    for event_time, raw_data, tier in all_rallies:
        raw = json.loads(raw_data)
        start_date = pd.to_datetime(raw['start_time']).date()
        rally_map[start_date] = {'tier': tier, 'gain': raw['gain']}
        if tier in ['DIAMOND', 'GOLD']:
            dg_dates.add(start_date)
    
    # Load data
    path_1d = coin_cell_paths.get_history_file('XVGUSDT', '1d')
    df_1d = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d['rsi'] = calculate_rsi(df_1d['close'])
    df_1d['ema9'] = df_1d['close'].ewm(span=9).mean()
    df_1d['ema21'] = df_1d['close'].ewm(span=21).mean()
    
    macd, macd_signal, hist = calculate_macd(df_1d['close'])
    df_1d['macd_hist'] = hist
    df_1d['macd_rising'] = hist > hist.shift(1)
    df_1d['atr'] = (df_1d['high'] - df_1d['low']) / df_1d['close'] * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    
    # Find Detector B false positives
    b_false_positives = []
    
    for idx in df_1d.index:
        if idx + 1 >= len(df_1d):
            continue
        
        if detector_b_momentum(df_1d, idx):
            sig_date = df_1d.loc[idx, 'datetime'].date()
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            
            if next_date not in dg_dates:
                # FALSE POSITIVE - analyze why
                sig = df_1d.loc[idx]
                next_day = df_1d.loc[idx+1]
                
                # What happened next day?
                next_gain = (next_day['high'] - sig['close']) / sig['close'] * 100
                next_tier = rally_map.get(next_date, {}).get('tier', 'NONE')
                actual_gain = rally_map.get(next_date, {}).get('gain', 0)
                
                # Get MACD color
                macd_color = 'N/A'
                if idx > 0:
                    prev = df_1d.loc[idx-1]
                    macd_color = get_macd_color(sig['macd_hist'], prev['macd_hist'])
                
                # Analyze failure reason
                reasons = []
                if next_tier == 'SILVER':
                    reasons.append(f"Only SILVER ({actual_gain:.1f}%)")
                elif next_tier == 'BRONZE':
                    reasons.append(f"Only BRONZE ({actual_gain:.1f}%)")
                elif next_tier == 'IRON':
                    reasons.append(f"IRON ({actual_gain:.1f}%)")
                elif next_tier == 'NONE':
                    reasons.append(f"NO RALLY (max gain {next_gain:.1f}%)")
               
                # Check if next day reversed
                if next_day['close'] < sig['close']:
                    reasons.append("Reversed down")
                
                # Check if RSI was too high
                if sig['rsi'] > 85:
                    reasons.append(f"RSI too hot ({sig['rsi']:.1f})")
                
                # Check volume
                if sig['vol_ratio'] < 1.5:
                    reasons.append(f"Low volume ({sig['vol_ratio']:.1f}x)")
                
                b_false_positives.append({
                    'date': sig_date.strftime('%Y-%m-%d'),
                    'rsi': sig['rsi'],
                    'macd_color': macd_color,
                    'body': abs(sig['close'] - sig['open']) / sig['open'] * 100,
                    'vol': sig['vol_ratio'],
                    'atr': sig['atr'],
                    'next_tier': next_tier,
                    'next_gain': next_gain,
                    'actual_gain': actual_gain,
                    'reasons': reasons
                })
    
    # Report
    print(f"\n🚫 DETECTOR B FALSE POSITIVES ({len(b_false_positives)} signals)")
    print("="*100)
    
    for i, fp in enumerate(b_false_positives, 1):
        print(f"{i:2}. {fp['date']}:")
        print(f"    Signal: RSI:{fp['rsi']:5.1f} | {fp['macd_color']} | Body:{fp['body']:5.1f}% | Vol:{fp['vol']:4.1f}x | ATR:{fp['atr']:5.1f}%")
        print(f"    Result: {fp['next_tier']} (actual gain {fp['actual_gain']:.1f}%, max {fp['next_gain']:.1f}%)")
        print(f"    Why Failed: {', '.join(fp['reasons'])}")
        print()
    
    # Aggregate failure patterns
    print("="*100)
    print("📊 FAILURE PATTERN ANALYSIS")
    print("="*100)
    
    tier_dist = {}
    for fp in b_false_positives:
        tier = fp['next_tier']
        tier_dist[tier] = tier_dist.get(tier, 0) + 1
    
    print(f"\nNext-Day Tier Distribution:")
    for tier, count in sorted(tier_dist.items(), key=lambda x: x[1], reverse=True):
        print(f"  {tier}: {count}")
    
    # RSI analysis
    rsis = [fp['rsi'] for fp in b_false_positives]
    if rsis:
        print(f"\nRSI Stats (False Positives):")
        print(f"  Average: {np.mean(rsis):.1f}")
        print(f"  Range: {min(rsis):.1f} - {max(rsis):.1f}")
    
    # Volume analysis
    vols = [fp['vol'] for fp in b_false_positives]
    if vols:
        print(f"\nVolume Stats:")
        print(f"  Average: {np.mean(vols):.1f}x")
        print(f"  Range: {min(vols):.1f}x - {max(vols):.1f}x")

if __name__ == "__main__":
    analyze_false_positives()
