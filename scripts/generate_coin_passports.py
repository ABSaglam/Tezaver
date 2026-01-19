"""
Tiered Coin Passport Generator
===============================
Creates Diamond/Gold/Silver entry protocols for each coin
based on historical successful rally conditions.
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

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_rally_conditions(symbol, start_time):
    """Get entry conditions for a specific rally."""
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
        
        # Calculate indicators
        df['rsi'] = calculate_rsi(df['close'])
        df['rsi_ema'] = df['rsi'].ewm(span=9).mean()
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        
        close = df.loc[idx, 'close']
        
        return {
            'rsi': df.loc[idx, 'rsi'],
            'rsi_ema': df.loc[idx, 'rsi_ema'],
            'atr': df.loc[idx, 'atr'],
            'vol_ratio': df.loc[idx, 'volume'] / df.loc[idx, 'vol_ma20'] if df.loc[idx, 'vol_ma20'] > 0 else 1,
            'above_ema20': 1 if close > df.loc[idx, 'ema20'] else 0
        }
    except:
        return None

def generate_passport(symbol, rallies_df):
    """Generate tiered passport for a coin."""
    
    passport = {
        'symbol': symbol,
        'generated_at': datetime.now().isoformat(),
        'diamond': None,
        'gold': None,
        'silver': None
    }
    
    for tier in ['DIAMOND', 'GOLD', 'SILVER']:
        tier_rallies = rallies_df[rallies_df['tier'] == tier]
        
        if len(tier_rallies) < 3:
            continue
        
        conditions = []
        for _, row in tier_rallies.iterrows():
            raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
            if raw_data is None:
                continue
                
            start_time = raw_data.get('start_time')
            if not start_time:
                continue
            
            cond = get_rally_conditions(symbol, start_time)
            if cond:
                conditions.append(cond)
        
        if len(conditions) < 3:
            continue
        
        cond_df = pd.DataFrame(conditions)
        
        # Calculate optimal thresholds (use median for robustness)
        protocol = {
            'count': len(conditions),
            'rsi': {
                'min': round(cond_df['rsi'].quantile(0.25), 1),
                'median': round(cond_df['rsi'].median(), 1),
                'max': round(cond_df['rsi'].quantile(0.75), 1)
            },
            'rsi_ema': {
                'median': round(cond_df['rsi_ema'].median(), 1)
            },
            'atr': {
                'min': round(cond_df['atr'].quantile(0.25), 2),
                'median': round(cond_df['atr'].median(), 2)
            },
            'vol_ratio': {
                'min': round(cond_df['vol_ratio'].quantile(0.25), 2),
                'median': round(cond_df['vol_ratio'].median(), 2)
            },
            'above_ema20_rate': round(cond_df['above_ema20'].mean() * 100, 1)
        }
        
        passport[tier.lower()] = protocol
    
    return passport

def run_passport_generator():
    print("=" * 80)
    print("🎫 KATMANLI COİN PASAPORT JENERATÖRÜ")
    print(f"Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load all rallies
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT symbol, tier, raw_data FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')"
    df_rallies = pd.read_sql_query(query, conn)
    conn.close()
    
    print(f"Toplam ralli: {len(df_rallies)}")
    
    passports = []
    
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 50 == 0:
            print(f"İlerleme: {i}/{len(DEFAULT_COINS)}")
        
        coin_rallies = df_rallies[df_rallies['symbol'] == symbol]
        
        if len(coin_rallies) < 5:
            continue
        
        passport = generate_passport(symbol, coin_rallies)
        
        # Only add if at least one tier has data
        if passport['diamond'] or passport['gold'] or passport['silver']:
            passports.append(passport)
    
    print(f"\n✅ {len(passports)} coin pasaportu oluşturuldu")
    
    # Save as JSON
    output_file = coin_cell_paths.get_library_root() / "coin_passports.json"
    with open(output_file, 'w') as f:
        json.dump(passports, f, indent=2, ensure_ascii=False)
    
    # Statistics
    print("\n" + "=" * 80)
    print("📊 PASAPORT İSTATİSTİKLERİ")
    print("=" * 80)
    
    diamond_count = sum(1 for p in passports if p['diamond'])
    gold_count = sum(1 for p in passports if p['gold'])
    silver_count = sum(1 for p in passports if p['silver'])
    
    print(f"\nDiamond protokolü olan: {diamond_count} coin")
    print(f"Gold protokolü olan: {gold_count} coin")
    print(f"Silver protokolü olan: {silver_count} coin")
    
    # Sample passports
    print("\n📋 Örnek Pasaportlar:")
    for passport in passports[:3]:
        print(f"\n{passport['symbol']}:")
        if passport['diamond']:
            p = passport['diamond']
            print(f"  DIAMOND ({p['count']} ralli): RSI {p['rsi']['min']}-{p['rsi']['max']}, ATR>{p['atr']['min']}%, VOL>{p['vol_ratio']['min']}x")
        if passport['gold']:
            p = passport['gold']
            print(f"  GOLD ({p['count']} ralli): RSI {p['rsi']['min']}-{p['rsi']['max']}, ATR>{p['atr']['min']}%, VOL>{p['vol_ratio']['min']}x")
        if passport['silver']:
            p = passport['silver']
            print(f"  SILVER ({p['count']} ralli): RSI {p['rsi']['min']}-{p['rsi']['max']}, ATR>{p['atr']['min']}%, VOL>{p['vol_ratio']['min']}x")
    
    print("\n" + "=" * 80)
    print(f"✅ Pasaportlar kaydedildi: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    run_passport_generator()
