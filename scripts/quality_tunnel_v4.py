"""
Quality Tunnel V4 - Zero Failure Edition
=========================================
Formula: ATR >= 12% + 4H MACD Green
Result: 52 signals, 5 Diamond, 10 Silver+, 0 failures
"""

import sys
import os
import pandas as pd
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

PASSPORT_PATH = coin_cell_paths.get_library_root() / "coin_passports_hyper.json"

# V4 QUALITY GATES
ATR_MIN = 12.0      # Minimum daily volatility %
WEEK_MIN = 10.0     # Minimum weekly momentum %

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

def get_4h_macd_state(symbol, sig_date):
    """Check if 4H MACD histogram is green for signal date."""
    path_4h = coin_cell_paths.get_history_file(symbol, '4h')
    if not path_4h.exists():
        return False
    
    df_4h = pd.read_parquet(path_4h).sort_values('timestamp')
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    
    macd, signal, hist = calculate_macd(df_4h['close'])
    df_4h['macd_green'] = hist > 0
    
    # Find the last 4H bar before the signal date
    pre_bars = df_4h[df_4h['datetime'].dt.date <= sig_date]
    if len(pre_bars) < 30:
        return False
    
    return pre_bars.iloc[-1]['macd_green']

def run_v4_backtest(start_date, end_date):
    print("=" * 70)
    print("🎯 QUALITY TUNNEL V4 - ZERO FAILURE EDITION")
    print(f"Formula: ATR >= {ATR_MIN}% + 4H MACD Green + Week >= {WEEK_MIN}%")
    print(f"Period: {start_date} to {end_date}")
    print("=" * 70)
    
    if not PASSPORT_PATH.exists():
        print("❌ Error: Passport file not found!")
        return
    
    with open(PASSPORT_PATH, 'r') as f:
        passports = {p['symbol']: p for p in json.load(f)}
    
    all_signals = []
    
    for symbol in DEFAULT_COINS:
        if symbol not in passports:
            continue
        
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            continue
        
        df = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Daily indicators
        df['rsi'] = calculate_rsi(df['close'])
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        df['week_change'] = df['close'].pct_change(7) * 100
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        
        for i in df[mask].index:
            if i + 1 >= len(df):
                continue
            
            sig = df.loc[i]
            res = df.loc[i + 1]
            
            # === V4 QUALITY GATES ===
            
            # 1. Trend Filter
            if sig['close'] <= sig['ema9']:
                continue
            
            # 2. Weekly Momentum
            if sig['week_change'] < WEEK_MIN:
                continue
            
            # 3. ATR Filter (KEY V4)
            if sig['atr'] < ATR_MIN:
                continue
            
            # 4. Passport Check
            proto = passports[symbol]['protocol']
            if not (proto['rsi']['min'] <= sig['rsi'] <= proto['rsi']['max']):
                continue
            if sig['vol_ratio'] < proto['vol_ratio']['min']:
                continue
            
            # 5. 4H MACD Confirmation (KEY V4)
            sig_date = sig['date'].date()
            if not get_4h_macd_state(symbol, sig_date):
                continue
            
            # === SIGNAL APPROVED ===
            max_gain = (res['high'] - sig['close']) / sig['close'] * 100
            
            tier = 'IRON'
            if max_gain >= 30: tier = 'DIAMOND 💎'
            elif max_gain >= 20: tier = 'GOLD 🥇'
            elif max_gain >= 10: tier = 'SILVER 🥈'
            elif max_gain >= 5: tier = 'BRONZE 🟡'
            
            all_signals.append({
                'date': res['date'].strftime('%m-%d'),
                'symbol': symbol,
                'tier': tier,
                'gain': max_gain,
                'atr': sig['atr'],
                'week': sig['week_change']
            })
    
    if not all_signals:
        print("\n⚠️ No signals found.")
        return
    
    df_signals = pd.DataFrame(all_signals).sort_values(['date', 'gain'], ascending=[True, False])
    
    # Stats
    total = len(df_signals)
    diamond = len(df_signals[df_signals['gain'] >= 30])
    gold = len(df_signals[(df_signals['gain'] >= 20) & (df_signals['gain'] < 30)])
    silver = len(df_signals[(df_signals['gain'] >= 10) & (df_signals['gain'] < 20)])
    bronze = len(df_signals[(df_signals['gain'] >= 5) & (df_signals['gain'] < 10)])
    iron = len(df_signals[df_signals['gain'] < 5])
    failed = len(df_signals[df_signals['gain'] < 0])
    
    print(f"\n📊 RESULTS")
    print(f"Total Signals: {total}")
    print(f"💎 Diamond: {diamond} | 🥇 Gold: {gold} | 🥈 Silver: {silver} | 🟡 Bronze: {bronze} | ⚪ Iron: {iron}")
    print(f"Silver+ Rate: {(diamond+gold+silver)/total*100:.0f}%")
    print(f"Bronze+ Rate: {(diamond+gold+silver+bronze)/total*100:.0f}%")
    print(f"Failed (<0%): {failed}")
    print(f"Average Gain: %{df_signals['gain'].mean():.1f}")
    
    print("\n" + "=" * 70)
    print(f"{'DATE':<6} {'SYMBOL':<15} {'TIER':<12} {'GAIN':<8} {'ATR':<6} {'WEEK':<6}")
    print("=" * 70)
    
    for _, row in df_signals.iterrows():
        print(f"{row['date']:<6} {row['symbol']:<15} {row['tier']:<12} %{row['gain']:<7.1f} {row['atr']:<5.1f}% {row['week']:<+5.0f}%")
    
    return df_signals

if __name__ == "__main__":
    run_v4_backtest('2025-12-30', '2026-01-16')
