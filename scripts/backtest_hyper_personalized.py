"""
Hyper-Personalized Backtest (Jan 2026)
=====================================
Uses tailored coin protocols from coin_passports_hyper.json.
"""

import sys
import os
import pandas as pd
import json
import sqlite3
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

PASSPORT_PATH = coin_cell_paths.get_library_root() / "coin_passports_hyper.json"
DB_PATH = coin_cell_paths.get_library_root() / "rallies.db"
TEST_START = '2026-01-01'
TEST_END = '2026-01-17'

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def check_hyper_passport(conditions, passport):
    proto = passport['protocol']
    
    # RSI: Must be within coin's comfort zone
    if not (proto['rsi']['min'] <= conditions['rsi'] <= proto['rsi']['max']):
        return False
        
    # ATR: Must be at least the coin's Q25
    if conditions['atr'] < proto['atr']['min']:
        return False
        
    # Vol Ratio: Must be at least the coin's Q25
    if conditions['vol_ratio'] < proto['vol_ratio']['min']:
        return False
        
    return True

def run_hyper_test():
    print("=" * 80)
    print("🏆 HYPER-PERSONALIZED TUNNEL BACKTEST (JANUARY 2026)")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    print("=" * 80)
    
    # 1. Load Passports
    if not PASSPORT_PATH.exists():
        print("❌ Error: Passports not found!")
        return
    with open(PASSPORT_PATH, 'r') as f:
        passports = {p['symbol']: p for p in json.load(f)}
    
    # 2. Get GROUND TRUTH (Actual Diamond/Gold/Silver rallies in Jan)
    conn = sqlite3.connect(DB_PATH)
    gt_query = f"SELECT symbol, tier, event_time, raw_data FROM rallies WHERE event_time >= '{TEST_START}' AND event_time <= '{TEST_END}' AND tier IN ('DIAMOND', 'GOLD', 'SILVER')"
    df_gt = pd.read_sql_query(gt_query, conn)
    conn.close()
    
    print(f"Ground Truth: Found {len(df_gt)} DSG rallies in the test period.")

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
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        df['week_change'] = df['close'].pct_change(7) * 100
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        
        # Filter Jan 2026 data
        mask = (df['date'] >= '2025-12-30') & (df['date'] <= '2026-01-16')
        target_indices = df[mask].index
        
        for i in target_indices:
            if i + 1 >= len(df): continue
            
            sig_row = df.loc[i]
            res_row = df.loc[i+1] # Next day result
            
            # CORE UNIVERSAL FILTERS
            if sig_row['close'] <= sig_row['ema9']: continue
            if sig_row['week_change'] < 10: continue # Weekly Momentum still required
            
            # HYPER PASSPORT CHECK
            cond = {
                'rsi': sig_row['rsi'],
                'atr': sig_row['atr'],
                'vol_ratio': sig_row['vol_ratio']
            }
            
            if check_hyper_passport(cond, passports[symbol]):
                max_gain = (res_row['high'] - sig_row['close']) / sig_row['close'] * 100
                
                all_signals.append({
                    'date': res_row['date'],
                    'symbol': symbol,
                    'week_change': sig_row['week_change'],
                    'rsi': sig_row['rsi'],
                    'max_gain': max_gain
                })

    if not all_signals:
        print("\n⚠️ No signals found.")
        return
        
    sig_df = pd.DataFrame(all_signals).sort_values('date')
    
    # 3. ANALYSIS
    print(f"\n📊 TOTAL SIGNALS: {len(sig_df)}")
    
    hits_10 = len(sig_df[sig_df['max_gain'] >= 10])
    hits_5 = len(sig_df[sig_df['max_gain'] >= 5])
    failed = len(sig_df[sig_df['max_gain'] <= 0])
    
    print(f"Diamond Hits (>10%): {hits_10}/{len(sig_df)} ({hits_10/len(sig_df)*100:.1f}%)")
    print(f"Target Hits (>5%):   {hits_5}/{len(sig_df)} ({hits_5/len(sig_df)*100:.1f}%)")
    print(f"Average Gain:        {sig_df['max_gain'].mean():.1f}%")
    print(f"Total Failed:        {failed}")
    
    # Recall Analysis (How many of the Jan GT rallies did we catch?)
    # This is slightly complex because signals happen T-1 and GT rallies are mapped to event_time
    caught = 0
    for _, rally in df_gt.iterrows():
        # A rally is 'caught' if we have a signal for that symbol on the day before or day of start_time
        r_time = pd.to_datetime(rally['event_time'])
        matches = sig_df[(sig_df['symbol'] == rally['symbol']) & 
                         (sig_df['date'].dt.date == r_time.date())]
        if not matches.empty:
            caught += 1
            
    print(f"Recall (DSG Rallies Caught): {caught}/{len(df_gt)} ({caught/len(df_gt)*100:.1f}%)")

    print("\n" + "-" * 80)
    print(f"{'DATE':6} {'SYMBOL':15} {'WEEK':6} {'RSI':4} {'MAX':7}")
    print("-" * 80)
    for _, row in sig_df.iterrows():
        status = '✅' if row['max_gain'] >= 10 else ('🟡' if row['max_gain'] >= 5 else '❌')
        print(f"{row['date'].strftime('%m-%d')} {row['symbol']:15} {row['week_change']:+5.0f}% {row['rsi']:3.0f} {row['max_gain']:+6.1f}% {status}")

if __name__ == "__main__":
    run_hyper_test()
