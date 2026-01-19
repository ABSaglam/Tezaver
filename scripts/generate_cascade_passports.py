"""
Cascade Passport Generator
===========================
If Diamond < 3 rallies, add to Gold pool
If Gold < 3 rallies, add to Silver pool
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import sqlite3
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"
TRAIN_END = '2025-12-31'

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_rally_conditions(symbol, start_time):
    try:
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            return None
        
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        
        start_ts = pd.to_datetime(start_time).timestamp() * 1000
        pre_idx = df[df['timestamp'] < start_ts].index
        
        if len(pre_idx) < 20:
            return None
        
        idx = pre_idx[-1]
        
        df['rsi'] = calculate_rsi(df['close'])
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        
        close = df.loc[idx, 'close']
        
        return {
            'rsi': df.loc[idx, 'rsi'],
            'atr': df.loc[idx, 'atr'],
            'vol_ratio': df.loc[idx, 'volume'] / df.loc[idx, 'vol_ma20'] if df.loc[idx, 'vol_ma20'] > 0 else 1,
            'above_ema20': 1 if close > df.loc[idx, 'ema20'] else 0
        }
    except:
        return None

def create_protocol(conditions):
    """Create protocol from conditions list."""
    if len(conditions) < 3:
        return None
    
    cond_df = pd.DataFrame(conditions)
    
    return {
        'count': len(conditions),
        'rsi': {
            'min': round(cond_df['rsi'].quantile(0.25), 1),
            'median': round(cond_df['rsi'].median(), 1),
            'max': round(cond_df['rsi'].quantile(0.75), 1)
        },
        'atr': {
            'min': round(cond_df['atr'].quantile(0.25), 2),
            'median': round(cond_df['atr'].median(), 2)
        },
        'vol_ratio': {
            'min': round(cond_df['vol_ratio'].quantile(0.25), 2),
            'median': round(cond_df['vol_ratio'].median(), 2)
        }
    }

def generate_cascade_passport(symbol, rallies_df):
    """Generate passport with cascade logic."""
    
    passport = {
        'symbol': symbol,
        'diamond': None,
        'gold': None,
        'silver': None
    }
    
    # Collect conditions for each tier
    tier_conditions = {'DIAMOND': [], 'GOLD': [], 'SILVER': []}
    
    for tier in ['DIAMOND', 'GOLD', 'SILVER']:
        tier_rallies = rallies_df[rallies_df['tier'] == tier]
        
        for _, row in tier_rallies.iterrows():
            raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
            if raw_data is None:
                continue
                
            start_time = raw_data.get('start_time')
            if not start_time:
                continue
            
            cond = get_rally_conditions(symbol, start_time)
            if cond:
                tier_conditions[tier].append(cond)
    
    # CASCADE LOGIC
    # If Diamond < 3, add to Gold
    if len(tier_conditions['DIAMOND']) < 3:
        tier_conditions['GOLD'].extend(tier_conditions['DIAMOND'])
    
    # If Gold < 3, add to Silver
    if len(tier_conditions['GOLD']) < 3:
        tier_conditions['SILVER'].extend(tier_conditions['GOLD'])
    
    # Create protocols
    if len(tier_conditions['DIAMOND']) >= 3:
        passport['diamond'] = create_protocol(tier_conditions['DIAMOND'])
    
    if len(tier_conditions['GOLD']) >= 3:
        passport['gold'] = create_protocol(tier_conditions['GOLD'])
    
    if len(tier_conditions['SILVER']) >= 3:
        passport['silver'] = create_protocol(tier_conditions['SILVER'])
    
    return passport

def run_cascade_generator():
    print("=" * 80)
    print("🎫 CASCADE PASAPORT JENERATÖRÜ")
    print(f"Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load training rallies only
    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT symbol, tier, raw_data FROM rallies 
        WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')
        AND event_time <= '{TRAIN_END}'
    """
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"Eğitim verisi: {len(df_rallies)} ralli (2024-2025)")
    
    passports = []
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 100 == 0:
            print(f"İlerleme: {i}/{len(DEFAULT_COINS)}")
        
        coin_rallies = df_rallies[df_rallies['symbol'] == symbol]
        
        if len(coin_rallies) < 3:
            continue
        
        passport = generate_cascade_passport(symbol, coin_rallies)
        
        if passport['diamond'] or passport['gold'] or passport['silver']:
            passports.append(passport)
    
    print(f"\n✅ {len(passports)} pasaport oluşturuldu")
    
    # Stats
    diamond_count = sum(1 for p in passports if p['diamond'])
    gold_count = sum(1 for p in passports if p['gold'])
    silver_count = sum(1 for p in passports if p['silver'])
    
    print(f"\nDiamond protokolü: {diamond_count} coin")
    print(f"Gold protokolü: {gold_count} coin")
    print(f"Silver protokolü: {silver_count} coin")
    
    # Save
    output_file = coin_cell_paths.get_library_root() / "coin_passports_cascade.json"
    with open(output_file, 'w') as f:
        json.dump(passports, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Kaydedildi: {output_file}")

if __name__ == "__main__":
    run_cascade_generator()
