"""
XVGUSDT Multi-Timeframe Diamond Deep Dive
==========================================
Analyzes Weekly, Daily, 4H for each Diamond.
Includes: RSI, RSI-EMA, MACD 4-color histogram, ATR
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
    """Get MACD histogram color (4 states)."""
    if hist_current > 0:
        if hist_current > hist_prev:
            return "GREEN_RISING 🟢↗"  # Bullish strengthening
        else:
            return "GREEN_FALLING 🟢↘"  # Bullish weakening
    else:
        if hist_current > hist_prev:
            return "RED_RISING 🔴↗"  # Bearish weakening
        else:
            return "RED_FALLING 🔴↘"  # Bearish strengthening

def add_full_indicators(df):
    """Add all indicators to dataframe."""
    df['rsi'] = calculate_rsi(df['close'])
    df['rsi_ema'] = df['rsi'].ewm(span=9).mean()
    df['rsi_vs_ema'] = df['rsi'] - df['rsi_ema']
    
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    
    macd, macd_signal, hist = calculate_macd(df['close'])
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['macd_hist'] = hist
    
    df['atr'] = (df['high'] - df['low']) / df['close'] * 100
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    
    return df

def deep_dive_diamond(event_time, raw_data, df_1d, df_4h, df_1w):
    """Multi-timeframe deep dive of a single Diamond."""
    raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    start_time = pd.to_datetime(raw['start_time'])
    gain = raw['gain']
    
    sig_date_1d = (start_time - timedelta(days=1)).date()
    
    report = {
        'diamond_date': event_time[:10],
        'gain': gain,
        'daily': None,
        'four_hour': None,
        'weekly': None
    }
    
    # === DAILY ===
    sig_rows_1d = df_1d[df_1d['datetime'].dt.date == sig_date_1d]
    if not sig_rows_1d.empty:
        sig = sig_rows_1d.iloc[0]
        sig_idx = sig_rows_1d.index[0]
        
        # MACD color
        macd_color = "N/A"
        if sig_idx > 0:
            prev = df_1d.loc[sig_idx-1]
            macd_color = get_macd_color(sig['macd_hist'], prev['macd_hist'])
        
        report['daily'] = {
            'date': sig_date_1d.strftime('%Y-%m-%d'),
            'rsi': sig['rsi'],
            'rsi_ema': sig['rsi_ema'],
            'rsi_vs_ema': sig['rsi_vs_ema'],
            'macd_hist': sig['macd_hist'],
            'macd_color': macd_color,
            'atr': sig['atr'],
            'vol_ratio': sig['vol_ratio'],
            'close_vs_ema9': ((sig['close'] - sig['ema9']) / sig['ema9'] * 100) if sig['ema9'] > 0 else 0
        }
    
    # === 4H ===
    if df_4h is not None and len(df_4h) > 0:
        pre_4h = df_4h[df_4h['datetime'] < start_time]
        if len(pre_4h) >= 2:
            last_4h = pre_4h.iloc[-1]
            prev_4h = pre_4h.iloc[-2]
            
            macd_color_4h = get_macd_color(last_4h['macd_hist'], prev_4h['macd_hist'])
            
            report['four_hour'] = {
                'datetime': last_4h['datetime'].strftime('%Y-%m-%d %H:%M'),
                'rsi': last_4h['rsi'],
                'rsi_ema': last_4h['rsi_ema'],
                'rsi_vs_ema': last_4h['rsi_vs_ema'],
                'macd_hist': last_4h['macd_hist'],
                'macd_color': macd_color_4h,
                'atr': last_4h['atr'],
                'close_vs_ema9': ((last_4h['close'] - last_4h['ema9']) / last_4h['ema9'] * 100) if last_4h['ema9'] > 0 else 0
            }
    
    # === WEEKLY ===
    if df_1w is not None and len(df_1w) > 0:
        week_rows = df_1w[df_1w['datetime'] <= start_time]
        if len(week_rows) >= 2:
            last_week = week_rows.iloc[-1]
            prev_week = week_rows.iloc[-2]
            
            macd_color_week = get_macd_color(last_week['macd_hist'], prev_week['macd_hist'])
            
            report['weekly'] = {
                'week_of': last_week['datetime'].strftime('%Y-%m-%d'),
                'rsi': last_week['rsi'],
                'rsi_ema': last_week['rsi_ema'],
                'rsi_vs_ema': last_week['rsi_vs_ema'],
                'macd_hist': last_week['macd_hist'],
                'macd_color': macd_color_week,
                'atr': last_week['atr'],
                'close_vs_ema9': ((last_week['close'] - last_week['ema9']) / last_week['ema9'] * 100) if last_week['ema9'] > 0 else 0
            }
    
    return report

def analyze_multi_timeframe():
    print("="*100)
    print("🔬 XVGUSDT - MULTI-TIMEFRAME DIAMOND DEEP DIVE")
    print("="*100)
    
    # Get Diamonds
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT event_time, raw_data FROM rallies 
        WHERE symbol = 'XVGUSDT' AND tier = 'DIAMOND'
        ORDER BY event_time
    """)
    diamonds = cursor.fetchall()
    conn.close()
    
    # Load all timeframes
    print("\nLoading data...")
    dfs = {}
    for tf in ['1d', '4h', '1w']:
        path = coin_cell_paths.get_history_file('XVGUSDT', tf)
        if path.exists():
            df = pd.read_parquet(path).sort_values('timestamp')
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = add_full_indicators(df)
            dfs[tf] = df
            print(f"  {tf}: {len(df)} bars")
    
    # Analyze each
    reports = []
    
    print(f"\n{'='*100}")
    print(f"Analyzing {len(diamonds)} Diamonds...\n")
    
    for i, (event_time, raw_data) in enumerate(diamonds, 1):
        report = deep_dive_diamond(
            event_time, raw_data,
            dfs.get('1d'),
            dfs.get('4h'),
            dfs.get('1w')
        )
        
        reports.append(report)
        
        print(f"{i:2}. 💎 {report['diamond_date']} → %{report['gain']:.1f}")
        print(f"{'─'*100}")
        
        # Daily
        if report['daily']:
            d = report['daily']
            print(f"  📊 DAILY ({d['date']}):")
            print(f"     RSI: {d['rsi']:5.1f} | RSI-EMA: {d['rsi_vs_ema']:+5.1f} | MACD: {d['macd_color']} {d['macd_hist']:+.3f}")
            print(f"     ATR: {d['atr']:5.1f}% | Vol: {d['vol_ratio']:4.1f}x | EMA9: {d['close_vs_ema9']:+.1f}%")
        
        # 4H
        if report['four_hour']:
            h = report['four_hour']
            print(f"  ⏰ 4H ({h['datetime']}):")
            print(f"     RSI: {h['rsi']:5.1f} | RSI-EMA: {h['rsi_vs_ema']:+5.1f} | MACD: {h['macd_color']} {h['macd_hist']:+.3f}")
            print(f"     ATR: {h['atr']:5.1f}% | EMA9: {h['close_vs_ema9']:+.1f}%")
        
        # Weekly
        if report['weekly']:
            w = report['weekly']
            print(f"  📅 WEEKLY (week of {w['week_of']}):")
            print(f"     RSI: {w['rsi']:5.1f} | RSI-EMA: {w['rsi_vs_ema']:+5.1f} | MACD: {w['macd_color']} {w['macd_hist']:+.3f}")
            print(f"     ATR: {w['atr']:5.1f}% | EMA9: {w['close_vs_ema9']:+.1f}%")
        
        print()
    
    # Save
    output_path = coin_cell_paths.get_library_root() / "xvg_multi_timeframe.json"
    with open(output_path, 'w') as f:
        json.dump(reports, f, indent=2, default=str)
    
    print(f"✅ Saved to: {output_path}")
    
    return reports

if __name__ == "__main__":
    reports = analyze_multi_timeframe()
