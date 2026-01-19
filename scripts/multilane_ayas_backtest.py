"""
Multi-Lane Ayaş Tüneli Backtest
================================
Uses coin passports for personalized entry conditions.
Generates daily signals and checks 24h outcomes.
"""

import sys
import os
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

# Load passports
PASSPORT_FILE = coin_cell_paths.get_library_root() / "coin_passports.json"
DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"

def load_passports():
    with open(PASSPORT_FILE, 'r') as f:
        passports = json.load(f)
    return {p['symbol']: p for p in passports}

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_passport_conditions(row, passport, tier='diamond'):
    """Check if current conditions match passport protocol."""
    protocol = passport.get(tier)
    if not protocol:
        return False
    
    rsi = row.get('rsi', 50)
    atr = row.get('atr', 10)
    vol_ratio = row.get('vol_ratio', 1)
    
    # RSI in range
    rsi_ok = protocol['rsi']['min'] <= rsi <= protocol['rsi']['max']
    
    # ATR above minimum
    atr_ok = atr >= protocol['atr']['min']
    
    # Volume above minimum
    vol_ok = vol_ratio >= protocol['vol_ratio']['min']
    
    # All conditions must be met
    return rsi_ok and atr_ok and vol_ok

def check_rally_within_24h(symbol, signal_date, tier_target):
    """Check if a rally of target tier happened within 24h of signal."""
    conn = sqlite3.connect(DB_PATH)
    
    signal_start = signal_date
    signal_end = signal_date + timedelta(hours=24)
    
    query = f"""
        SELECT tier, raw_data FROM rallies 
        WHERE symbol = '{symbol}' 
        AND event_time >= '{signal_start}'
        AND event_time <= '{signal_end}'
        AND tier IN ('DIAMOND', 'GOLD', 'SILVER')
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return None, 0
    
    # Get best tier achieved
    tier_order = {'DIAMOND': 3, 'GOLD': 2, 'SILVER': 1}
    best_tier = max(df['tier'].tolist(), key=lambda x: tier_order.get(x, 0))
    
    # Calculate max gain
    max_gain = 0
    for _, row in df.iterrows():
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        if raw_data and 'gain' in raw_data:
            max_gain = max(max_gain, raw_data.get('gain', 0))
    
    return best_tier, max_gain

def run_backtest():
    print("=" * 80)
    print("🚇 ÇOK ŞERİTLİ AYAŞ TÜNELİ BACKTEST")
    print(f"Başlangıç: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    passports = load_passports()
    print(f"Yüklenen pasaport: {len(passports)} coin")
    
    all_signals = []
    
    # Process each coin
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 50 == 0:
            print(f"İlerleme: {i}/{len(DEFAULT_COINS)} coin")
        
        if symbol not in passports:
            continue
        
        passport = passports[symbol]
        
        # Load daily data
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            continue
        
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        
        if len(df) < 30:
            continue
        
        # Calculate indicators
        df['rsi'] = calculate_rsi(df['close'])
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        
        # Check each day
        for idx in range(30, len(df)):
            row = df.iloc[idx]
            
            conditions = {
                'rsi': row['rsi'],
                'atr': row['atr'],
                'vol_ratio': row['vol_ratio'] if not pd.isna(row['vol_ratio']) else 1
            }
            
            # Check Diamond protocol
            if check_passport_conditions(conditions, passport, 'diamond'):
                signal_date = pd.to_datetime(row['timestamp'], unit='ms')
                tier_achieved, gain = check_rally_within_24h(symbol, signal_date, 'DIAMOND')
                
                all_signals.append({
                    'symbol': symbol,
                    'date': signal_date,
                    'target': 'DIAMOND',
                    'achieved': tier_achieved,
                    'gain': gain,
                    'rsi': row['rsi'],
                    'atr': row['atr'],
                    'vol_ratio': row['vol_ratio']
                })
    
    df_signals = pd.DataFrame(all_signals)
    
    print(f"\n✅ Toplam sinyal: {len(df_signals)}")
    
    # Results
    print("\n" + "=" * 80)
    print("📊 BACKTEST SONUÇLARI")
    print("=" * 80)
    
    if df_signals.empty:
        print("Sinyal bulunamadı!")
        return
    
    # Success rates
    hit_any = df_signals[df_signals['achieved'].notna()]
    hit_diamond = df_signals[df_signals['achieved'] == 'DIAMOND']
    hit_gold = df_signals[df_signals['achieved'] == 'GOLD']
    hit_silver = df_signals[df_signals['achieved'] == 'SILVER']
    
    total = len(df_signals)
    
    print(f"\n🎯 Hedef: DIAMOND")
    print(f"Toplam Sinyal: {total}")
    print(f"24h içinde Ralli Olan: {len(hit_any)} ({len(hit_any)/total*100:.1f}%)")
    print(f"  - Diamond: {len(hit_diamond)} ({len(hit_diamond)/total*100:.1f}%)")
    print(f"  - Gold: {len(hit_gold)} ({len(hit_gold)/total*100:.1f}%)")
    print(f"  - Silver: {len(hit_silver)} ({len(hit_silver)/total*100:.1f}%)")
    
    if len(hit_any) > 0:
        avg_gain = hit_any['gain'].mean()
        max_gain = hit_any['gain'].max()
        print(f"\nOrtalama Kazanç: {avg_gain:.1f}%")
        print(f"Maksimum Kazanç: {max_gain:.1f}%")
    
    # Top performers
    print("\n📊 En Çok Sinyal Veren Coinler:")
    top_coins = df_signals.groupby('symbol').size().nlargest(10)
    for sym, count in top_coins.items():
        sym_signals = df_signals[df_signals['symbol'] == sym]
        sym_hits = sym_signals[sym_signals['achieved'].notna()]
        hit_rate = len(sym_hits) / count * 100 if count > 0 else 0
        print(f"   {sym:15s}: {count:4d} sinyal, {hit_rate:.1f}% başarı")
    
    # Save results
    output_file = coin_cell_paths.get_library_root() / "multilane_backtest_results.csv"
    df_signals.to_csv(output_file, index=False)
    
    print("\n" + "=" * 80)
    print(f"✅ Sonuçlar kaydedildi: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    run_backtest()
