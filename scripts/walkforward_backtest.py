"""
Walk-Forward Backtest
======================
Proper out-of-sample test:
- Train passports on 2024-2025 data only
- Test on unseen January 2026 data
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

DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"
TRAIN_END = '2025-12-31'  # Train on data before this date
TEST_START = '2026-01-01'  # Test on data after this date

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

def generate_passport_from_train(symbol, train_rallies):
    """Generate passport from training data only."""
    
    passport = {
        'symbol': symbol,
        'diamond': None,
        'gold': None,
        'silver': None
    }
    
    for tier in ['DIAMOND', 'GOLD', 'SILVER']:
        tier_rallies = train_rallies[train_rallies['tier'] == tier]
        
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
        
        protocol = {
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
        
        passport[tier.lower()] = protocol
    
    return passport

def check_passport_conditions(row, passport, tier='diamond'):
    """Check if conditions match passport protocol."""
    protocol = passport.get(tier)
    if not protocol:
        return False
    
    rsi = row.get('rsi', 50)
    atr = row.get('atr', 10)
    vol_ratio = row.get('vol_ratio', 1)
    
    rsi_ok = protocol['rsi']['min'] <= rsi <= protocol['rsi']['max']
    atr_ok = atr >= protocol['atr']['min']
    vol_ok = vol_ratio >= protocol['vol_ratio']['min']
    
    return rsi_ok and atr_ok and vol_ok

def check_rally_within_24h(symbol, signal_date):
    """Check if a rally happened within 24h of signal."""
    conn = sqlite3.connect(DB_PATH)
    
    signal_end = signal_date + timedelta(hours=24)
    
    query = f"""
        SELECT tier, raw_data FROM rallies 
        WHERE symbol = '{symbol}' 
        AND event_time >= '{signal_date}'
        AND event_time <= '{signal_end}'
        AND tier IN ('DIAMOND', 'GOLD', 'SILVER')
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        return None, 0
    
    tier_order = {'DIAMOND': 3, 'GOLD': 2, 'SILVER': 1}
    best_tier = max(df['tier'].tolist(), key=lambda x: tier_order.get(x, 0))
    
    max_gain = 0
    for _, row in df.iterrows():
        raw_data = eval(row['raw_data']) if isinstance(row['raw_data'], str) else row['raw_data']
        if raw_data and 'gain' in raw_data:
            max_gain = max(max_gain, raw_data.get('gain', 0))
    
    return best_tier, max_gain

def run_walk_forward():
    print("=" * 80)
    print("🚇 WALK-FORWARD BACKTEST")
    print(f"Eğitim: 2024-{TRAIN_END} | Test: {TEST_START}-2026-01-17")
    print("=" * 80)
    
    # Load all rallies
    conn = sqlite3.connect(DB_PATH)
    df_all_rallies = pd.read_sql_query(
        "SELECT symbol, tier, event_time, raw_data FROM rallies WHERE tier IN ('DIAMOND', 'GOLD', 'SILVER')",
        conn
    )
    conn.close()
    
    df_all_rallies['event_time'] = pd.to_datetime(df_all_rallies['event_time'])
    
    # Split train/test
    train_rallies = df_all_rallies[df_all_rallies['event_time'] <= TRAIN_END]
    test_rallies = df_all_rallies[df_all_rallies['event_time'] >= TEST_START]
    
    print(f"Eğitim verisi: {len(train_rallies)} ralli")
    print(f"Test verisi: {len(test_rallies)} ralli")
    
    # Generate passports from TRAINING data only
    print("\n📝 Pasaportlar oluşturuluyor (sadece 2024-2025 verisi)...")
    
    passports = {}
    for i, symbol in enumerate(DEFAULT_COINS, 1):
        if i % 100 == 0:
            print(f"   {i}/{len(DEFAULT_COINS)}")
        
        coin_train = train_rallies[train_rallies['symbol'] == symbol]
        
        if len(coin_train) < 5:
            continue
        
        passport = generate_passport_from_train(symbol, coin_train)
        
        if passport['diamond'] or passport['gold'] or passport['silver']:
            passports[symbol] = passport
    
    print(f"✅ {len(passports)} pasaport oluşturuldu")
    
    # Test on January 2026
    print("\n🧪 Test ediliyor (Ocak 2026)...")
    
    all_signals = []
    
    for symbol in passports.keys():
        passport = passports[symbol]
        
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            continue
        
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Filter to test period
        test_df = df[(df['date'] >= TEST_START) & (df['date'] <= '2026-01-17')]
        
        if test_df.empty:
            continue
        
        # Calculate indicators
        df['rsi'] = calculate_rsi(df['close'])
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        
        # Check each day in test period
        for idx in test_df.index:
            if idx not in df.index:
                continue
            
            row = df.loc[idx]
            
            conditions = {
                'rsi': row['rsi'] if not pd.isna(row['rsi']) else 50,
                'atr': row['atr'] if not pd.isna(row['atr']) else 10,
                'vol_ratio': row['vol_ratio'] if not pd.isna(row['vol_ratio']) else 1
            }
            
            if check_passport_conditions(conditions, passport, 'diamond'):
                signal_date = pd.to_datetime(row['timestamp'], unit='ms')
                tier_achieved, gain = check_rally_within_24h(symbol, signal_date)
                
                all_signals.append({
                    'symbol': symbol,
                    'date': signal_date,
                    'achieved': tier_achieved,
                    'gain': gain
                })
    
    df_signals = pd.DataFrame(all_signals)
    
    # Results
    print("\n" + "=" * 80)
    print("📊 WALK-FORWARD SONUÇLARI (Gerçek Out-of-Sample)")
    print("=" * 80)
    
    if df_signals.empty:
        print("Sinyal bulunamadı!")
        return
    
    total = len(df_signals)
    hit_any = df_signals[df_signals['achieved'].notna()]
    hit_diamond = df_signals[df_signals['achieved'] == 'DIAMOND']
    hit_gold = df_signals[df_signals['achieved'] == 'GOLD']
    hit_silver = df_signals[df_signals['achieved'] == 'SILVER']
    
    print(f"\n🎯 OCAK 2026 (Görülmemiş Veri):")
    print(f"Toplam Sinyal: {total}")
    print(f"24h içinde Ralli Olan: {len(hit_any)} ({len(hit_any)/total*100:.1f}%)")
    print(f"  - Diamond: {len(hit_diamond)} ({len(hit_diamond)/total*100:.1f}%)")
    print(f"  - Gold: {len(hit_gold)} ({len(hit_gold)/total*100:.1f}%)")
    print(f"  - Silver: {len(hit_silver)} ({len(hit_silver)/total*100:.1f}%)")
    
    if len(hit_any) > 0:
        print(f"\nOrtalama Kazanç: {hit_any['gain'].mean():.1f}%")
        print(f"Maksimum Kazanç: {hit_any['gain'].max():.1f}%")
    
    # Show all signals
    print("\n📋 TÜM SİNYALLER:")
    df_signals = df_signals.sort_values('date')
    for _, row in df_signals.iterrows():
        achieved = row['achieved'] if pd.notna(row['achieved']) else 'MISS'
        gain = f"{row['gain']:.1f}%" if pd.notna(row['gain']) and row['gain'] > 0 else '-'
        print(f"   {row['date'].strftime('%Y-%m-%d')} {row['symbol']:15s} → {achieved:8s} ({gain})")
    
    # Save
    output_file = coin_cell_paths.get_library_root() / "walkforward_results.csv"
    df_signals.to_csv(output_file, index=False)
    
    print("\n" + "=" * 80)
    print(f"✅ Sonuçlar kaydedildi: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    run_walk_forward()
