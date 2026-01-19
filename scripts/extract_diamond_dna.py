"""
Diamond Formation DNA Extractor
================================
Surgeon-level precision analysis of 59 January 2026 Diamonds.
Extracts the complete formation pattern, rhythm, and soul of each rally.
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

def extract_formation_dna(symbol, rally_start_time, timeframe='1d', lookback_days=7):
    """Extract the complete formation pattern before a rally."""
    path = coin_cell_paths.get_history_file(symbol, timeframe)
    if not path.exists():
        return None
    
    df = pd.read_parquet(path).sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Add all indicators
    df['rsi'] = calculate_rsi(df['close'])
    df['rsi_ema'] = df['rsi'].ewm(span=9).mean()
    df['ema9'] = df['close'].ewm(span=9).mean()
    df['ema21'] = df['close'].ewm(span=21).mean()
    df['ema50'] = df['close'].ewm(span=50).mean()
    
    macd, macd_signal, hist = calculate_macd(df['close'])
    df['macd'] = macd
    df['macd_signal'] = macd_signal
    df['macd_hist'] = hist
    
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma20']
    df['atr'] = (df['high'] - df['low']) / df['close'] * 100
    
    # Price change metrics
    df['price_change_1d'] = df['close'].pct_change(1) * 100
    df['price_change_3d'] = df['close'].pct_change(3) * 100
    df['price_change_7d'] = df['close'].pct_change(7) * 100
    
    # Find formation window (lookback_days before rally)
    rally_ts = pd.to_datetime(rally_start_time)
    start_window = rally_ts - timedelta(days=lookback_days)
    
    formation = df[(df['datetime'] >= start_window) & (df['datetime'] <= rally_ts)]
    
    if len(formation) < 3:
        return None
    
    # Extract pattern
    pattern = {
        'timeframe': timeframe,
        'bars': len(formation),
        'data': []
    }
    
    for idx, row in formation.iterrows():
        bar = {
            'date': row['datetime'].strftime('%Y-%m-%d %H:%M'),
            'close': float(row['close']),
            'rsi': float(row['rsi']),
            'rsi_ema': float(row['rsi_ema']),
            'macd_hist': float(row['macd_hist']),
            'vol_ratio': float(row['vol_ratio']),
            'atr': float(row['atr']),
            'price_1d': float(row['price_change_1d']) if not pd.isna(row['price_change_1d']) else 0,
            'price_7d': float(row['price_change_7d']) if not pd.isna(row['price_change_7d']) else 0,
            'ema9': float(row['ema9']),
            'ema21': float(row['ema21'])
        }
        pattern['data'].append(bar)
    
    # Calculate formation characteristics
    last_bar = pattern['data'][-1]
    first_bar = pattern['data'][0]
    
    # Momentum buildup
    rsi_trend = last_bar['rsi'] - first_bar['rsi']
    macd_trend = last_bar['macd_hist'] - first_bar['macd_hist']
    vol_surge = max([b['vol_ratio'] for b in pattern['data']])
    
    # EMA alignment (bullish when 9 > 21)
    ema_bullish = last_bar['ema9'] > last_bar['ema21']
    
    pattern['characteristics'] = {
        'rsi_buildup': rsi_trend,
        'macd_momentum': macd_trend,
        'max_vol_surge': vol_surge,
        'ema_aligned': ema_bullish,
        'final_rsi': last_bar['rsi'],
        'final_macd_hist': last_bar['macd_hist'],
        'final_vol_ratio': last_bar['vol_ratio'],
        'final_atr': last_bar['atr']
    }
    
    return pattern

def analyze_diamond_formations():
    print("=" * 80)
    print("💎 DIAMOND FORMATION DNA EXTRACTOR - OCAK 2026")
    print("Hedef: 59 Diamond'ın tam oluşum sürecini çözmek")
    print("=" * 80)
    
    # Get all January 2026 Diamonds
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, tier, event_time, raw_data FROM rallies 
        WHERE event_time >= '2026-01-01' AND event_time <= '2026-01-31' 
        AND tier = 'DIAMOND'
        ORDER BY event_time
    """)
    diamonds = cursor.fetchall()
    conn.close()
    
    print(f"\n📊 Toplam Diamond: {len(diamonds)}")
    print("\n🔬 Oluşum süreci analizi başlıyor...\n")
    
    formations = []
    
    for i, (symbol, tier, event_time, raw_data) in enumerate(diamonds, 1):
        raw = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
        rally_start = raw['start_time']
        gain = raw.get('gain', 0)
        
        print(f"[{i}/{len(diamonds)}] {symbol} - %{gain:.1f} - {event_time[:10]}")
        
        # Extract formation patterns from multiple timeframes
        daily = extract_formation_dna(symbol, rally_start, '1d', lookback_days=7)
        four_h = extract_formation_dna(symbol, rally_start, '4h', lookback_days=3)
        hourly = extract_formation_dna(symbol, rally_start, '1h', lookback_days=2)
        
        formation = {
            'symbol': symbol,
            'event_time': event_time,
            'gain': gain,
            'rally_start': rally_start,
            'formations': {
                '1d': daily,
                '4h': four_h,
                '1h': hourly
            }
        }
        
        formations.append(formation)
    
    # Save raw data
    output_path = coin_cell_paths.get_library_root() / "diamond_formation_dna.json"
    with open(output_path, 'w') as f:
        json.dump(formations, f, indent=2)
    
    print(f"\n✅ DNA verisi kaydedildi: {output_path}")
    
    # Analyze patterns
    print("\n" + "=" * 80)
    print("📊 ORTAK PATTERN ANALİZİ")
    print("=" * 80)
    
    # Collect all daily characteristics
    chars = []
    for f in formations:
        if f['formations']['1d'] and f['formations']['1d']['characteristics']:
            char = f['formations']['1d']['characteristics']
            char['symbol'] = f['symbol']
            char['gain'] = f['gain']
            chars.append(char)
    
    df_chars = pd.DataFrame(chars)
    
    if len(df_chars) > 0:
        print("\n--- GÜNLÜK OLUŞUM ORTALMALARI ---")
        print(f"RSI Build-up: {df_chars['rsi_buildup'].mean():.1f}")
        print(f"MACD Momentum: {df_chars['macd_momentum'].mean():.2f}")
        print(f"Max Vol Surge: {df_chars['max_vol_surge'].mean():.1f}x")
        print(f"EMA Aligned: {df_chars['ema_aligned'].sum()}/{len(df_chars)} ({df_chars['ema_aligned'].sum()/len(df_chars)*100:.0f}%)")
        print(f"\n--- RALLI BAŞLANGICI DEĞERLER ---")
        print(f"Final RSI: {df_chars['final_rsi'].mean():.1f} (min: {df_chars['final_rsi'].min():.1f}, max: {df_chars['final_rsi'].max():.1f})")
        print(f"Final MACD Histogram: {df_chars['final_macd_hist'].mean():.3f}")
        print(f"Final Vol Ratio: {df_chars['final_vol_ratio'].mean():.1f}x")
        print(f"Final ATR: {df_chars['final_atr'].mean():.1f}%")
        
        # Find common patterns
        print("\n--- ORTAK ÖZELLIKLER ---")
        high_rsi_buildup = len(df_chars[df_chars['rsi_buildup'] > 10])
        positive_macd = len(df_chars[df_chars['final_macd_hist'] > 0])
        high_vol = len(df_chars[df_chars['max_vol_surge'] > 2])
        
        print(f"RSI Yükseliş (>10): {high_rsi_buildup}/{len(df_chars)} ({high_rsi_buildup/len(df_chars)*100:.0f}%)")
        print(f"Pozitif MACD: {positive_macd}/{len(df_chars)} ({positive_macd/len(df_chars)*100:.0f}%)")
        print(f"Yüksek Hacim (>2x): {high_vol}/{len(df_chars)} ({high_vol/len(df_chars)*100:.0f}%)")
    
    return formations

if __name__ == "__main__":
    formations = analyze_diamond_formations()
    print("\n✅ Analiz tamamlandı. Detaylar: library/diamond_formation_dna.json")
