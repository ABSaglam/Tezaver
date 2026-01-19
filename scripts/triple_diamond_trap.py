"""
Triple Diamond Trap System
==========================
Trap 1: Hot Diamonds (RSI > 65, high momentum)
Trap 2: Cold Diamonds (reversal with 2+ triggers)
Trap 3: Silent Risers (stealth momentum buildup)
"""

import sys
import os
import pandas as pd
import json
import sqlite3

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

def calculate_macd(prices, fast=12, slow=26, signal=9):
    ema_fast = prices.ewm(span=fast).mean()
    ema_slow = prices.ewm(span=slow).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def hot_trap(sig):
    """HOT: Overheated, high momentum."""
    if sig['rsi'] > 65 and sig['close'] > sig['ema9'] and sig['vol_ratio'] >= 1:
        return True, "HOT"
    return False, None

def cold_trap(sig):
    """COLD: Reversal with 2+ explosive triggers."""
    triggers = []
    if sig['vol_ratio'] >= 3: triggers.append("VOL")
    if sig['atr'] >= 20: triggers.append("ATR")
    if sig['macd_hist'] > 0 and sig['macd_rising']: triggers.append("MACD")
    if sig['rsi_change_1d'] > 10: triggers.append("RSI_JUMP")
    
    if len(triggers) >= 2:
        return True, f"COLD:{'+'.join(triggers)}"
    return False, None

def silent_riser_trap(sig, df, idx):
    """SILENT: Stealth momentum buildup in downtrend."""
    # Must be in downtrend or sideways (not strong uptrend)
    if sig['close'] > sig['ema9']:
        return False, None
    
    # Check momentum buildup over last 3-7 days
    if idx < 7:
        return False, None
    
    recent = df.iloc[idx-7:idx+1]
    
    # RSI buildup: +10 points over 7 days
    rsi_buildup = recent['rsi'].iloc[-1] - recent['rsi'].iloc[0]
    if rsi_buildup < 10:
        return False, None
    
    # Volume gradual increase
    vol_trend = recent['vol_ratio'].iloc[-3:].mean() > recent['vol_ratio'].iloc[:3].mean()
    
    # Price stabilization (ATR decreasing or stable)
    recent_atr = recent['atr'].iloc[-3:].mean()
    earlier_atr = recent['atr'].iloc[:3].mean()
    atr_stable = recent_atr <= earlier_atr * 1.2
    
    # MACD turning positive or rising
    macd_improving = sig['macd_hist'] > recent['macd_hist'].iloc[0]
    
    # Need at least 2 of these stealth signals
    signals = []
    if rsi_buildup >= 15: signals.append("RSI_BUILD")
    if vol_trend: signals.append("VOL_BUILD")
    if atr_stable and recent_atr >= 5: signals.append("ATR_STABLE")
    if macd_improving: signals.append("MACD_RISE")
    if sig['rsi'] >= 45 and sig['rsi'] <= 64: signals.append("RSI_READY")
    
    if len(signals) >= 2:
        return True, f"SILENT:{'+'.join(signals)}"
    
    return False, None

def run_triple_trap():
    print("=" * 80)
    print("🎯 TRIPLE DIAMOND TRAP SYSTEM")
    print("=" * 80)
    
    # Get all Diamonds
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
        diamond_dict[key] = {'gain': raw['gain'], 'event_time': event_time}
    
    print(f"Target: {len(diamonds)} Diamonds\n")
    
    hot_caught = []
    cold_caught = []
    silent_caught = []
    all_signals = []
    
    for symbol in DEFAULT_COINS:
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
        
        for idx in df[mask].index:
            if idx + 1 >= len(df):
                continue
            
            sig = df.loc[idx]
            
            # Try all three traps
            hot_pass, hot_reason = hot_trap(sig)
            cold_pass, cold_reason = cold_trap(sig)
            silent_pass, silent_reason = silent_riser_trap(sig, df, idx)
            
            if hot_pass or cold_pass or silent_pass:
                sig_key = f"{symbol}_{sig['date'].date()}"
                is_diamond = sig_key in diamond_dict
                
                if is_diamond:
                    dia_info = diamond_dict[sig_key]
                    gain = dia_info['gain']
                else:
                    res = df.loc[idx+1]
                    gain = (res['high'] - sig['close']) / sig['close'] * 100
                
                trap = 'HOT' if hot_pass else ('COLD' if cold_pass else 'SILENT')
                reason = hot_reason or cold_reason or silent_reason
                
                signal = {
                    'symbol': symbol,
                    'date': sig['date'].strftime('%m-%d'),
                    'trap': trap,
                    'reason': reason,
                    'is_diamond': is_diamond,
                    'gain': gain
                }
                
                all_signals.append(signal)
                
                if is_diamond:
                    if hot_pass:
                        hot_caught.append(signal)
                    elif cold_pass:
                        cold_caught.append(signal)
                    else:
                        silent_caught.append(signal)
    
    total_caught = len(hot_caught) + len(cold_caught) + len(silent_caught)
    
    print(f"📊 RESULTS")
    print(f"HOT: {len([s for s in all_signals if s['trap'] == 'HOT'])} signals, {len(hot_caught)} Diamonds")
    print(f"COLD: {len([s for s in all_signals if s['trap'] == 'COLD'])} signals, {len(cold_caught)} Diamonds")
    print(f"SILENT: {len([s for s in all_signals if s['trap'] == 'SILENT'])} signals, {len(silent_caught)} Diamonds")
    print(f"\nTOTAL: {len(all_signals)} signals, {total_caught}/{len(diamonds)} Diamonds ({total_caught/len(diamonds)*100:.0f}%)")
    
    print(f"\n✅ SILENT TRAP DIAMONDS ({len(silent_caught)}):")
    for s in sorted(silent_caught, key=lambda x: x['gain'], reverse=True)[:15]:
        print(f"  {s['date']} {s['symbol']:15} %{s['gain']:6.1f} - {s['reason']}")
    
    return all_signals, total_caught, len(diamonds)

if __name__ == "__main__":
    signals, caught, total = run_triple_trap()
    print(f"\n🎯 FINAL: {caught}/{total} Diamonds = {caught/total*100:.0f}% yakalama oranı")
