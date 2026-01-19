"""
Quality-Filtered Hyper-Personalized Tunnel (V3)
================================================
Final production version with ATR quality gate.
Filters: ATR >= 18%, Week >= 20%, + Coin-specific RSI/Vol protocols
"""

import sys
import os
import pandas as pd
import json
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

PROFILE_PATH = coin_cell_paths.get_library_root() / "coin_behavior_profiles.json"
PASSPORT_PATH = coin_cell_paths.get_library_root() / "coin_passports_hyper.json"

# QUALITY GATES (V3)
ATR_MIN = 18.0      # Minimum daily volatility %
WEEK_MIN = 20.0     # Minimum weekly momentum %

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def score_signal(symbol, cond, profiles, passports):
    if symbol not in profiles:
        return 0
    prof = profiles[symbol]
    score = 60
    
    # RSI proximity to median (max 15 pts)
    rsi_dist = abs(cond['rsi'] - prof['rsi']['median'])
    score += max(0, 15 - (rsi_dist * 0.5))
    
    # Volume strength (max 15 pts)
    vol_min = passports[symbol].get('protocol', {}).get('vol_ratio', {}).get('min', 0.8)
    if vol_min > 0:
        score += min(15, (cond['vol_ratio'] / vol_min - 1) * 10)
    
    # Momentum bonus (max 10 pts)
    score += min(10, max(0, (cond['week_change'] - WEEK_MIN) * 0.5))
    
    return min(100, round(score))

def check_passport(symbol, cond, passports):
    """Check if conditions match the coin's personalized protocol."""
    if symbol not in passports:
        return False
    proto = passports[symbol]['protocol']
    
    if not (proto['rsi']['min'] <= cond['rsi'] <= proto['rsi']['max']):
        return False
    if cond['vol_ratio'] < proto['vol_ratio']['min']:
        return False
    
    return True

def generate_signals(start_date, end_date):
    """Generate quality-filtered signals for a date range."""
    
    if not PROFILE_PATH.exists() or not PASSPORT_PATH.exists():
        print("❌ Error: Profile or Passport files not found!")
        return []
    
    with open(PROFILE_PATH, 'r') as f:
        profiles = json.load(f)
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
        
        # Calculate indicators
        df['rsi'] = calculate_rsi(df['close'])
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        df['week_change'] = df['close'].pct_change(7) * 100
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        
        # Filter date range
        mask = (df['date'] >= start_date) & (df['date'] <= end_date)
        
        for i in df[mask].index:
            if i + 1 >= len(df):
                continue
                
            sig = df.loc[i]
            
            # === QUALITY GATES ===
            # 1. Trend Filter
            if sig['close'] <= sig['ema9']:
                continue
                
            # 2. ATR Filter (NEW V3)
            if sig['atr'] < ATR_MIN:
                continue
                
            # 3. Weekly Momentum Filter (UPGRADED)
            if sig['week_change'] < WEEK_MIN:
                continue
            
            # 4. Passport Check (Personalized)
            cond = {
                'rsi': sig['rsi'],
                'vol_ratio': sig['vol_ratio'],
                'week_change': sig['week_change'],
                'atr': sig['atr']
            }
            
            if not check_passport(symbol, cond, passports):
                continue
            
            # === SIGNAL APPROVED ===
            score = score_signal(symbol, cond, profiles, passports)
            
            all_signals.append({
                'date': sig['date'],
                'symbol': symbol,
                'score': score,
                'rsi': sig['rsi'],
                'atr': sig['atr'],
                'week_change': sig['week_change'],
                'vol_ratio': sig['vol_ratio'],
                'close': sig['close']
            })
    
    return all_signals

def run_backtest(start_date, end_date):
    """Run backtest with quality filters."""
    print("=" * 60)
    print(f"🎯 QUALITY TUNNEL V3 BACKTEST")
    print(f"Filters: ATR >= {ATR_MIN}% | Week >= {WEEK_MIN}%")
    print(f"Period: {start_date} to {end_date}")
    print("=" * 60)
    
    signals = generate_signals(start_date, end_date)
    
    if not signals:
        print("No signals found.")
        return
    
    # Load data for results
    results = []
    for sig in signals:
        path_1d = coin_cell_paths.get_history_file(sig['symbol'], '1d')
        df = pd.read_parquet(path_1d).sort_values('timestamp')
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Find next day
        next_rows = df[df['date'] > sig['date']].head(1)
        if next_rows.empty:
            continue
            
        next_day = next_rows.iloc[0]
        max_gain = (next_day['high'] - sig['close']) / sig['close'] * 100
        
        tier = 'IRON'
        if max_gain >= 30: tier = 'DIAMOND 💎'
        elif max_gain >= 20: tier = 'GOLD 🥇'
        elif max_gain >= 10: tier = 'SILVER 🥈'
        elif max_gain >= 5: tier = 'BRONZE 🟡'
        
        results.append({
            'Date': next_day['date'].strftime('%m-%d'),
            'Symbol': sig['symbol'],
            'Tier': tier,
            'Gain': f"%{max_gain:.1f}",
            'Score': sig['score'],
            'gain_val': max_gain
        })
    
    df_results = pd.DataFrame(results).sort_values(['Date', 'Score'], ascending=[True, False])
    
    # Stats
    total = len(df_results)
    diamond = len(df_results[df_results['gain_val'] >= 30])
    gold = len(df_results[df_results['gain_val'] >= 20])
    silver = len(df_results[df_results['gain_val'] >= 10])
    bronze = len(df_results[df_results['gain_val'] >= 5])
    
    print(f"\n📊 RESULTS")
    print(f"Total Signals: {total}")
    print(f"Diamond: {diamond} | Gold: {gold-diamond} | Silver: {silver-gold} | Bronze: {bronze-silver} | Iron: {total-bronze}")
    print(f"Silver+ Rate: {silver/total*100:.0f}%")
    print(f"Bronze+ Rate: {bronze/total*100:.0f}%")
    print(f"Average Gain: %{df_results['gain_val'].mean():.1f}")
    print()
    print(df_results[['Date', 'Symbol', 'Tier', 'Gain', 'Score']].to_string(index=False))

if __name__ == "__main__":
    # Default: January 2026 backtest
    run_backtest('2025-12-30', '2026-01-16')
