import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
SOUL_PATH = "/Users/alisaglam/TezaverMac/ignition_soul_manifest.json"

with open(SOUL_PATH, "r") as f:
    SOUL = json.load(f)

def get_threshold(symbol):
    return SOUL.get(symbol, 5.0)

def analyze_sequence(df, i, symbol):
    if i + 2 >= len(df): return False
    t0, t1, t2 = df.iloc[i], df.iloc[i+1], df.iloc[i+2]
    
    # T0: Ignition
    v_ratio0 = t0['volume'] / (t0['vol_ma50'] or 0.001)
    if v_ratio0 < get_threshold(symbol): return False
    
    # T1: Heat
    v_ratio1 = t1['volume'] / (t1['vol_ma50'] or 0.001)
    if v_ratio1 < 2.0: return False
    if t1['close'] < t0['open']: return False
    
    # T2: Burn
    if t2['rsi'] < t0['rsi']: return False
    if t2['rsi_ema'] <= t1['rsi_ema']: return False
    
    return True

def run_audit():
    symbols = [d for d in os.listdir(COIN_CELLS_DIR) if d.endswith("USDT")]
    all_signals = []
    
    print(f"Scanning {len(symbols)} symbols for 2026...")
    
    for symbol in symbols:
        p = f"{COIN_CELLS_DIR}/{symbol}/data/history_15m.parquet"
        if not os.path.exists(p): continue
        
        df = pd.read_parquet(p)
        df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('dt', inplace=True)
        df = df[df.index.year == 2026]
        if df.empty: continue
        
        # Techs
        df['vol_ma50'] = df['volume'].rolling(50).mean()
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).ewm(alpha=1/11, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/11, adjust=False).mean().replace(0, 0.001)
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))
        df['rsi_ema'] = df['rsi'].ewm(span=11, adjust=False).mean()
        
        for i in range(50, len(df) - 192): # Need 48h (192 bars) forward
            if analyze_sequence(df, i, symbol):
                entry_p = df['close'].iloc[i+2] # T+2 Close
                # Look 48h ahead for Peak
                future = df.iloc[i+3 : i+195]
                if future.empty: continue
                
                max_p = future['high'].max()
                gain_pct = ((max_p / entry_p) - 1) * 100
                
                tier = "NONE"
                if gain_pct >= 50: tier = "DIAMOND 💎"
                elif gain_pct >= 20: tier = "GOLD 🥇"
                elif gain_pct >= 10: tier = "SILVER 🥈"
                elif gain_pct >= 5: tier = "BRONZE 🥉"
                
                all_signals.append({
                    'symbol': symbol,
                    'time': df.index[i+2],
                    'gain': gain_pct,
                    'tier': tier
                })
        
    if not all_signals:
        print("No signals found.")
        return

    res = pd.DataFrame(all_signals)
    
    print("\n--- 📊 2026 IGNITOR PERFORMANCE AUDIT ---")
    print(f"Total Signals: {len(res)}")
    print("\n[TIER DISTRIBUTION]")
    print(res['tier'].value_counts())
    
    print("\n[PROFITABILITY SLICES]")
    print(f"Rallies > 100%: {len(res[res['gain'] >= 100])}")
    print(f"Rallies > 50%:  {len(res[res['gain'] >= 50])}")
    print(f"Rallies > 20%:  {len(res[res['gain'] >= 20])}")
    print(f"Small Peaks (5-10%): {len(res[(res['gain'] >= 5) & (res['gain'] < 10)])}")
    
    # Define Loss as failure to reach 3% gain before something bad happens? 
    # Or just simply MAX < 3%?
    losses = res[res['gain'] < 3.0]
    print(f"\n[LOSS AUDIT]")
    print(f"Total Fails (Max Gain < 3%): {len(losses)} ({len(losses)/len(res)*100:.1f}%)")
    
    res.to_csv("ignitor_2026_audit_results.csv")
    print("\nResults saved to ignitor_2026_audit_results.csv")

if __name__ == "__main__":
    run_audit()
