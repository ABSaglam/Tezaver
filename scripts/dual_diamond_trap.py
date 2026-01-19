"""
Dual Diamond Trap System
========================
Trap 1: Hot Diamonds (RSI > 65, high momentum)
Trap 2: Cold Diamonds (RSI < 65, reversal patterns)
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

def hot_diamond_trap(sig_row):
    """Trap for high-momentum, overheated diamonds."""
    # RSI > 65 (overheated state)
    if sig_row['rsi'] <= 65:
        return False, "RSI not hot"
    
    # Must be in uptrend
    if sig_row['close'] <= sig_row['ema9']:
        return False, "Not in uptrend"
    
    # At least some volume
    if sig_row['vol_ratio'] < 1:
        return False, "Low volume"
    
    return True, "HOT"

def cold_diamond_trap(sig_row):
    """Trap for reversal/breakout diamonds from cold state."""
    # RSI < 65 (not overheated)
    if sig_row['rsi'] > 65:
        return False, "Too hot"
    
    # Looking for reversal patterns - multiple triggers:
    triggers = []
    
    # 1. Volume explosion (>3x)
    if sig_row['vol_ratio'] >= 3:
        triggers.append("VOL_SURGE")
    
    # 2. High ATR (>20% - volatility breakout)
    if sig_row['atr'] >= 20:
        triggers.append("ATR_BREAKOUT")
    
    # 3. MACD turning positive (momentum shift)
    if sig_row['macd_hist'] > 0 and sig_row['macd_rising']:
        triggers.append("MACD_TURN")
    
    # 4. RSI surge (>10 point jump in one day)
    if sig_row['rsi_change_1d'] > 10:
        triggers.append("RSI_SURGE")
    
    # Need at least 2 triggers
    if len(triggers) >= 2:
        return True, f"COLD: {'+'.join(triggers)}"
    
    return False, f"Only {len(triggers)} trigger(s)"

def run_dual_trap_test():
    print("=" * 80)
    print("🎯 DUAL DIAMOND TRAP SYSTEM - TEST")
    print("=" * 80)
    
    # Load passports (for basic filters)
    with open(PASSPORT_PATH, 'r') as f:
        passports = {p['symbol']: p for p in json.load(f)}
    
    # Get ground truth Diamonds
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, event_time, raw_data FROM rallies 
        WHERE event_time >= '2026-01-01' AND event_time <= '2026-01-31' 
        AND tier = 'DIAMOND'
    """)
    diamonds = cursor.fetchall()
    conn.close()
    
    diamond_dict = {}
    for symbol, event_time, raw_data in diamonds:
        raw = json.loads(raw_data)
        start_date = pd.to_datetime(raw['start_time']).date()
        key = f"{symbol}_{start_date}"
        diamond_dict[key] = raw['gain']
    
    print(f"Target: {len(diamonds)} Diamonds\n")
    
    # Test on all signals
    hot_caught = []
    cold_caught = []
    all_signals = []
    
    for symbol in DEFAULT_COINS:
        if symbol not in passports:
            continue
        
        path_1d = coin_cell_paths.get_history_file(symbol, '1d')
        if not path_1d.exists():
            continue
        
        df = pd.read_parquet(path_1d).sort_values('timestamp').reset_index(drop=True)
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['rsi'] = calculate_rsi(df['close'])
        df['rsi_change_1d'] = df['rsi'].diff()
        df['ema9'] = df['close'].ewm(span=9).mean()
        df['vol_ma20'] = df['volume'].rolling(20).mean()
        df['vol_ratio'] = df['volume'] / df['vol_ma20']
        df['atr'] = (df['high'] - df['low']) / df['close'] * 100
        
        macd, macd_signal, hist = calculate_macd(df['close'])
        df['macd'] = macd
        df['macd_signal'] = macd_signal
        df['macd_hist'] = hist
        df['macd_rising'] = hist > hist.shift(1)
        
        mask = (df['date'] >= '2025-12-30') & (df['date'] <= '2026-01-16')
        
        for i in df[mask].index:
            if i + 1 >= len(df):
                continue
            
            sig = df.loc[i]
            res = df.loc[i + 1]
            
            # Try both traps
            hot_pass, hot_reason = hot_diamond_trap(sig)
            cold_pass, cold_reason = cold_diamond_trap(sig)
            
            if hot_pass or cold_pass:
                sig_key = f"{symbol}_{sig['date'].date()}"
                is_diamond = sig_key in diamond_dict
                gain = diamond_dict.get(sig_key, (res['high'] - sig['close']) / sig['close'] * 100)
                
                signal = {
                    'date': res['date'].strftime('%m-%d'),
                    'symbol': symbol,
                    'trap': 'HOT' if hot_pass else 'COLD',
                    'reason': hot_reason if hot_pass else cold_reason,
                    'is_diamond': is_diamond,
                    'gain': gain
                }
                
                all_signals.append(signal)
                
                if is_diamond:
                    if hot_pass:
                        hot_caught.append(signal)
                    else:
                        cold_caught.append(signal)
    
    # Results
    total_caught = len(hot_caught) + len(cold_caught)
    
    print(f"📊 RESULTS")
    print(f"HOT Trap: {len([s for s in all_signals if s['trap'] == 'HOT'])} signals, {len(hot_caught)} Diamonds")
    print(f"COLD Trap: {len([s for s in all_signals if s['trap'] == 'COLD'])} signals, {len(cold_caught)} Diamonds")
    print(f"TOTAL: {len(all_signals)} signals, {total_caught}/{len(diamonds)} Diamonds ({total_caught/len(diamonds)*100:.0f}%)")
    
    print(f"\n✅ HOT DIAMONDS CAUGHT ({len(hot_caught)}):")
    for s in sorted(hot_caught, key=lambda x: x['gain'], reverse=True)[:10]:
        print(f"  {s['date']} {s['symbol']:15} %{s['gain']:.1f}")
    
    print(f"\n✅ COLD DIAMONDS CAUGHT ({len(cold_caught)}):")
    for s in sorted(cold_caught, key=lambda x: x['gain'], reverse=True)[:10]:
        print(f"  {s['date']} {s['symbol']:15} %{s['gain']:.1f} - {s['reason']}")
    
    return all_signals

if __name__ == "__main__":
    signals = run_dual_trap_test()
