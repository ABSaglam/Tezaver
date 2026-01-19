"""
XVGUSDT Diamond Pre-Day Soul Reader
====================================
Reads the soul of each Diamond's pre-rally day.
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

def read_pre_diamond_day(event_time, raw_data, df):
    """Read the soul of the day before a Diamond."""
    raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    start_time = pd.to_datetime(raw['start_time'])
    gain = raw['gain']
    
    # Day before
    sig_date = (start_time - timedelta(days=1)).date()
    sig_rows = df[df['datetime'].dt.date == sig_date]
    
    if sig_rows.empty:
        return None
    
    sig = sig_rows.iloc[0]
    sig_idx = sig_rows.index[0]
    
    # Get 7-day context
    if sig_idx < 7:
        return None
    
    week = df.iloc[sig_idx-6:sig_idx+1]
    
    # Candle characteristics
    body = abs(sig['close'] - sig['open']) / sig['open'] * 100
    upper_wick = (sig['high'] - max(sig['open'], sig['close'])) / sig['open'] * 100
    lower_wick = (min(sig['open'], sig['close']) - sig['low']) / sig['open'] * 100
    candle_color = 'GREEN 🟢' if sig['close'] > sig['open'] else 'RED 🔴'
    
    # Position
    close_vs_ema9 = ((sig['close'] - sig['ema9']) / sig['ema9'] * 100) if sig['ema9'] > 0 else 0
    close_vs_ema21 = ((sig['close'] - sig['ema21']) / sig['ema21'] * 100) if sig['ema21'] > 0 else 0
    
    # Momentum
    rsi_7d_change = sig['rsi'] - week['rsi'].iloc[0]
    price_7d_change = ((sig['close'] / week['close'].iloc[0]) - 1) * 100
    
    soul = {
        'date': event_time[:10],
        'gain': gain,
        'sig_date': sig_date.strftime('%Y-%m-%d'),
        # Candle
        'candle': candle_color,
        'body': body,
        'upper_wick': upper_wick,
        'lower_wick': lower_wick,
        # Indicators
        'rsi': sig['rsi'],
        'rsi_7d_change': rsi_7d_change,
        'macd_hist': sig['macd_hist'],
        'macd_rising': sig['macd_rising'],
        'vol_ratio': sig['vol_ratio'],
        'atr': sig['atr'],
        # Position
        'close_vs_ema9': close_vs_ema9,
        'close_vs_ema21': close_vs_ema21,
        # 7-day context
        'price_7d': price_7d_change,
        'rsi_min_7d': week['rsi'].min(),
        'rsi_max_7d': week['rsi'].max(),
        'vol_max_7d': week['vol_ratio'].max()
    }
    
    return soul

def analyze_all_diamonds():
    print("="*90)
    print("🔮 XVGUSDT - READING THE SOUL OF EACH DIAMOND")
    print("="*90)
    
    # Get all Diamonds
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_time, raw_data FROM rallies 
        WHERE symbol = 'XVGUSDT' AND tier = 'DIAMOND'
        ORDER BY event_time
    """)
    diamonds = cursor.fetchall()
    conn.close()
    
    # Load price data
    path = coin_cell_paths.get_history_file('XVGUSDT', '1d')
    df = pd.read_parquet(path).sort_values('timestamp')
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Add indicators
    df['rsi'] = calculate_rsi(df['close'])
    df['rsi_ema'] = df['rsi'].ewm(span=9).mean()
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    
    macd, macd_signal, hist = calculate_macd(df['close'])
    df['macd_hist'] = hist
    df['macd_rising'] = hist > hist.shift(1)
    
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['atr'] = (df['high'] - df['low']) / df['close'] * 100
    
    # Analyze each
    souls = []
    
    print(f"\nAnalyzing {len(diamonds)} Diamonds...\n")
    
    for i, (event_time, raw_data) in enumerate(diamonds, 1):
        soul = read_pre_diamond_day(event_time, raw_data, df)
        
        if soul:
            souls.append(soul)
            
            print(f"{i:2}. 💎 {soul['date']} → %{soul['gain']:6.1f}")
            print(f"    Pre-Day: {soul['sig_date']}")
            print(f"    Candle: {soul['candle']} | Body:{soul['body']:5.1f}% UWick:{soul['upper_wick']:4.1f}% LWick:{soul['lower_wick']:4.1f}%")
            print(f"    RSI: {soul['rsi']:5.1f} (7d change: {soul['rsi_7d_change']:+5.1f}) | Range: {soul['rsi_min_7d']:.0f}-{soul['rsi_max_7d']:.0f}")
            print(f"    Vol: {soul['vol_ratio']:4.1f}x (7d max: {soul['vol_max_7d']:.1f}x) | ATR: {soul['atr']:5.1f}%")
            print(f"    MACD: {'▲' if soul['macd_rising'] else '▼'} {soul['macd_hist']:+.3f}")
            print(f"    Position: EMA9 {soul['close_vs_ema9']:+.1f}% | EMA21 {soul['close_vs_ema21']:+.1f}%")
            print(f"    7-Day Price: {soul['price_7d']:+.1f}%")
            print()
    
    # Aggregate patterns
    if souls:
        print("="*90)
        print("📊 AGGREGATE DIAMOND PRE-DAY SIGNATURE")
        print("="*90)
        
        green_count = sum(1 for s in souls if 'GREEN' in s['candle'])
        print(f"\nCandle Color: {green_count}/{len(souls)} GREEN ({green_count/len(souls)*100:.0f}%)")
        print(f"Avg Body: {np.mean([s['body'] for s in souls]):.1f}%")
        print(f"Avg Upper Wick: {np.mean([s['upper_wick'] for s in souls]):.1f}%")
        print(f"Avg Lower Wick: {np.mean([s['lower_wick'] for s in souls]):.1f}%")
        print(f"\nRSI: {np.mean([s['rsi'] for s in souls]):.1f} (range: {min(s['rsi'] for s in souls):.0f}-{max(s['rsi'] for s in souls):.0f})")
        print(f"RSI 7d Change: {np.mean([s['rsi_7d_change'] for s in souls]):+.1f}")
        print(f"\nVol Ratio: {np.mean([s['vol_ratio'] for s in souls]):.1f}x")
        print(f"ATR: {np.mean([s['atr'] for s in souls]):.1f}%")
        print(f"\nMACD Rising: {sum(1 for s in souls if s['macd_rising'])}/{len(souls)}")
        print(f"\nAbove EMA9: {sum(1 for s in souls if s['close_vs_ema9'] > 0)}/{len(souls)} ({sum(1 for s in souls if s['close_vs_ema9'] > 0)/len(souls)*100:.0f}%)")
        print(f"Avg EMA9 Distance: {np.mean([s['close_vs_ema9'] for s in souls]):+.1f}%")
        print(f"\n7-Day Price Change: {np.mean([s['price_7d'] for s in souls]):+.1f}%")
    
    return souls

if __name__ == "__main__":
    souls = analyze_all_diamonds()
    
    # Save
    output_path = coin_cell_paths.get_library_root() / "xvg_diamond_souls.json"
    with open(output_path, 'w') as f:
        json.dump(souls, f, indent=2, default=str)
    
    print(f"\n✅ Saved to: {output_path}")
