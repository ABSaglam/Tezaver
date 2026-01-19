"""
Final Precision Backtest (Jan 2026)
=====================================
Uses expanded 2023-2025 dataset, cascade passports, 
and weekly momentum filter.
"""

import sys
import os
import pandas as pd
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

PASSPORT_PATH = coin_cell_paths.get_library_root() / "coin_passports_cascade.json"
TEST_START = '2026-01-01'
TEST_END = '2026-01-17'

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_passport(symbol, conditions, passport, tier):
    protocol = passport.get(tier)
    if not protocol:
        return False
        
    # Standard Passport Check
    if not (protocol['rsi']['min'] * 0.9 <= conditions['rsi'] <= protocol['rsi']['max'] * 1.1):
        return False
    if conditions['atr'] < protocol['atr']['min'] * 0.9:
        return False
    if conditions['vol_ratio'] < protocol['vol_ratio']['min'] * 0.9:
        return False
        
    return True

def run_final_test():
    print("=" * 80)
    print("🏆 FINAL PRECISION BACKTEST (JANUARY 2026)")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # Load Passports
    if not PASSPORT_PATH.exists():
        print("❌ Error: Passports not found!")
        return
        
    with open(PASSPORT_PATH, 'r') as f:
        passports = {p['symbol']: p for p in json.load(f)}
    
    all_signals = []
    
    for symbol in DEFAULT_COINS:
        if symbol not in passports:
            continue
            
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        path_4h = coin_cell_paths.get_history_file(symbol, '4h')
        
        if not path_1d.exists() or not path_4h.exists():
            continue
            
        df = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Indicators
        df['rsi'] = calculate_rsi(df['close'])
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['ema20'] = df['close'].ewm(span=20).mean()
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        df['week_change'] = df['close'].pct_change(7) * 100
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        
        df_4h = pd.read_parquet(path_4h).sort_values('timestamp').reset_index(drop=True)
        df_4h['date'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
        df_4h['ema9'] = df_4h['close'].ewm(span=9).mean()
        
        # Filter Jan 2026 signals (Signals on T, results on T+1)
        mask = (df['date'] >= '2025-12-31') & (df['date'] <= '2026-01-16')
        target_indices = df[mask].index
        
        for i in target_indices:
            if i + 1 >= len(df):
                continue
                
            sig_row = df.loc[i]
            res_row = df.loc[i + 1]
            
            # 1. CORE FILTERS (High Precision Rules)
            if sig_row['close'] <= sig_row['ema9']: continue
            if sig_row['week_change'] < 10: continue # Weekly Momentum > 10%
            if sig_row['rsi'] > 72: continue
            if sig_row['vol_ratio'] < 1.0: continue
            
            # 2. 4H Trend Verification
            mask_4h = df_4h['date'] <= sig_row['date']
            if not mask_4h.any(): continue
            last_4h = df_4h[mask_4h].iloc[-1]
            if last_4h['close'] <= last_4h['ema9']: continue
            
            # 3. PASSPORT VERIFICATION (Diamond Preferred)
            cond = {
                'rsi': sig_row['rsi'],
                'atr': sig_row['atr'],
                'vol_ratio': sig_row['vol_ratio']
            }
            
            passport = passports[symbol]
            target_tier = 'NONE'
            if check_passport(symbol, cond, passport, 'diamond'):
                target_tier = 'DIAMOND'
            elif check_passport(symbol, cond, passport, 'gold'):
                target_tier = 'GOLD'
                
            if target_tier == 'NONE':
                continue
            
            max_gain = (res_row['high'] - sig_row['close']) / sig_row['close'] * 100
            
            all_signals.append({
                'date': res_row['date'],
                'symbol': symbol,
                'tier': target_tier,
                'week_change': sig_row['week_change'],
                'rsi': sig_row['rsi'],
                'max_gain': max_gain
            })

    # Results table
    if not all_signals:
        print("\n⚠️ No signals found with current filters.")
        return
        
    df_res = pd.DataFrame(all_signals).sort_values('date')
    print(f"\n📊 Total Signals: {len(df_res)}")
    
    hit_10 = len(df_res[df_res['max_gain'] >= 10])
    hit_5 = len(df_res[df_res['max_gain'] >= 5])
    loss = len(df_res[df_res['max_gain'] <= 0])
    
    print(f"Diamond Hits (>10%): {hit_10}/{len(df_res)} ({hit_10/len(df_res)*100:.1f}%)")
    print(f"Goal Hits (>5%): {hit_5}/{len(df_res)} ({hit_5/len(df_res)*100:.1f}%)")
    print(f"Average Max Gain: {df_res['max_gain'].mean():.1f}%")
    print(f"Total Failed (<=0%): {loss}")
    print("\n" + "-" * 80)
    print(f"{'DATE':6} {'SYMBOL':15} {'TIER':8} {'WEEK':6} {'RSI':4} {'MAX':7}")
    print("-" * 80)
    
    for _, row in df_res.iterrows():
        status = '✅' if row['max_gain'] >= 10 else ('🟡' if row['max_gain'] >= 5 else '❌')
        print(f"{row['date'].strftime('%m-%d')} {row['symbol']:15} {row['tier']:8} {row['week_change']:+5.0f}% {row['rsi']:3.0f} {row['max_gain']:+6.1f}% {status}")

if __name__ == "__main__":
    run_final_test()
