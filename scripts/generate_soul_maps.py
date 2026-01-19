"""
Complete Soul Map Generator
============================
Deep multi-timeframe analysis of top DSG producers.
Creates comprehensive soul profiles - how each coin breathes, runs, lives.
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

def analyze_formation_soul(symbol, rally, df_1d, df_4h, df_1w):
    """Analyze the soul of a single rally formation."""
    start_time = pd.to_datetime(rally['start_time'])
    sig_date = start_time - timedelta(days=1)
    
    soul = {
        'tier': rally['tier'],
        'gain': rally['gain'],
        'date': rally['event_time'][:10]
    }
    
    # === DAILY ANALYSIS (7 days before) ===
    sig_rows = df_1d[df_1d['datetime'].dt.date == sig_date.date()]
    if not sig_rows.empty:
        sig_idx = sig_rows.index[0]
        
        if sig_idx >= 7:
            week = df_1d.iloc[sig_idx-6:sig_idx+1]
            
            # Capture the 7-day journey
            soul['daily'] = {
                'rsi_start': week['rsi'].iloc[0],
                'rsi_end': week['rsi'].iloc[-1],
                'rsi_change': week['rsi'].iloc[-1] - week['rsi'].iloc[0],
                'rsi_min': week['rsi'].min(),
                'rsi_max': week['rsi'].max(),
                'price_change_7d': ((week['close'].iloc[-1] / week['close'].iloc[0]) - 1) * 100,
                'vol_avg': week['volume'].mean(),
                'vol_max': week['volume'].max(),
                'atr_avg': week['atr'].mean()
            }
            
            # Rhythm: Is it accelerating or decelerating?
            early_momentum = week['close'].iloc[1:4].pct_change().mean()
            late_momentum = week['close'].iloc[4:].pct_change().mean()
            
            if late_momentum > early_momentum * 1.5:
                soul['daily']['rhythm'] = 'ACCELERATING'
            elif late_momentum < early_momentum * 0.5:
                soul['daily']['rhythm'] = 'DECELERATING'
            else:
                soul['daily']['rhythm'] = 'STEADY'
    
    # === 4H ANALYSIS (last 48h) ===
    if df_4h is not None and len(df_4h) > 0:
        pre_4h = df_4h[df_4h['datetime'] < start_time]
        if len(pre_4h) >= 12:
            last_48h = pre_4h.iloc[-12:]
            
            # Heartbeat pattern
            pulses = last_48h['close'].pct_change().dropna()
            
            soul['4h'] = {
                'pulse_avg': pulses.mean() * 100,
                'pulse_std': pulses.std() * 100,
                'rsi_final': last_48h['rsi'].iloc[-1],
                'volatility': 'HIGH' if pulses.std() > 0.05 else ('MEDIUM' if pulses.std() > 0.02 else 'LOW')
            }
    
    # === WEEKLY CONTEXT ===
    if df_1w is not None and len(df_1w) > 0:
        week_rows = df_1w[df_1w['datetime'] <= start_time]
        if len(week_rows) >= 4:
            last_4w = week_rows.iloc[-4:]
            
            soul['weekly'] = {
                'trend': 'BULL' if last_4w['close'].iloc[-1] > last_4w['close'].iloc[0] else 'BEAR',
                'rsi': week_rows.iloc[-1]['rsi'],
                'momentum_4w': ((last_4w['close'].iloc[-1] / last_4w['close'].iloc[0]) - 1) * 100
            }
    
    return soul

def create_soul_map(symbol):
    """Create complete soul map for a coin."""
    print(f"\n{'='*90}")
    print(f"🔮 CREATING SOUL MAP FOR {symbol}")
    print(f"{'='*90}")
    
    # Get ALL DSG rallies
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT tier, event_time, raw_data FROM rallies 
        WHERE symbol = '{symbol}' AND tier IN ('DIAMOND', 'SILVER', 'GOLD')
        ORDER BY event_time
    """)
    rallies = cursor.fetchall()
    conn.close()
    
    if not rallies:
        print(f"❌ No DSG rallies for {symbol}")
        return None
    
    print(f"Found {len(rallies)} DSG rallies")
    
    # Load price data
    paths = {
        '1d': coin_cell_paths.get_history_file(symbol, '1d'),
        '4h': coin_cell_paths.get_history_file(symbol, '4h'),
        '1w': coin_cell_paths.get_history_file(symbol, '1w')
    }
    
    data = {}
    for tf, path in paths.items():
        if path.exists():
            df = pd.read_parquet(path).sort_values('timestamp')
            df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['rsi'] = calculate_rsi(df['close'])
            df['atr'] = (df['high'] - df['low']) / df['close'] * 100
            data[tf] = df
    
    if '1d' not in data:
        print(f"❌ No price data")
        return None
    
    # Analyze each rally
    souls = []
    for tier, event_time, raw_data in rallies[:50]:  # Limit to 50 for performance
        raw = json.loads(raw_data)
        rally = {'tier': tier, 'event_time': event_time, 'gain': raw['gain'], 'start_time': raw['start_time']}
        
        soul = analyze_formation_soul(
            symbol, rally,
            data['1d'],
            data.get('4h'),
            data.get('1w')
        )
        
        if soul:
            souls.append(soul)
    
    # Aggregate patterns
    diamonds = [s for s in souls if s['tier'] == 'DIAMOND']
    golds = [s for s in souls if s['tier'] == 'GOLD']
    silvers = [s for s in souls if s['tier'] == 'SILVER']
    
    profile = {
        'symbol': symbol,
        'total_dsg': len(souls),
        'diamonds': len(diamonds),
        'golds': len(golds),
        'silvers': len(silvers),
        'souls': souls
    }
    
    # Analyze patterns
    if souls:
        daily_souls = [s for s in souls if 'daily' in s]
        
        if daily_souls:
            profile['patterns'] = {
                'avg_rsi_start': np.mean([s['daily']['rsi_start'] for s in daily_souls]),
                'avg_rsi_end': np.mean([s['daily']['rsi_end'] for s in daily_souls]),
                'avg_rsi_change': np.mean([s['daily']['rsi_change'] for s in daily_souls]),
                'avg_price_7d': np.mean([s['daily']['price_change_7d'] for s in daily_souls]),
                'common_rhythm': max(set([s['daily']['rhythm'] for s in daily_souls]), key=[s['daily']['rhythm'] for s in daily_souls].count)
            }
            
            print(f"\n📊 SOUL PATTERNS:")
            print(f"  RSI Journey: {profile['patterns']['avg_rsi_start']:.1f} → {profile['patterns']['avg_rsi_end']:.1f} ({profile['patterns']['avg_rsi_change']:+.1f})")
            print(f"  7-Day Price: {profile['patterns']['avg_price_7d']:+.1f}%")
            print(f"  Common Rhythm: {profile['patterns']['common_rhythm']}")
    
    return profile

def generate_soul_report(symbols):
    """Generate comprehensive report for multiple coins."""
    all_profiles = []
    
    for symbol in symbols:
        profile = create_soul_map(symbol)
        if profile:
            all_profiles.append(profile)
    
    # Save
    output_path = coin_cell_paths.get_library_root() / "soul_maps.json"
    with open(output_path, 'w') as f:
        json.dump(all_profiles, f, indent=2, default=str)
    
    print(f"\n✅ Soul maps saved to: {output_path}")
    return all_profiles

if __name__ == "__main__":
    # Top 10 DSG producers (from DB query)
    top_10 = [
        'PEPEUSDT', 'RAYUSDT', 'SYNUSDT', 'BONKUSDT', 'FTTUSDT',
        'MAVUSDT', 'WLDUSDT', 'ARKMUSDT', 'FLOKIUSDT', 'VANRYUSDT'
    ]
    
    profiles = generate_soul_report(top_10)
