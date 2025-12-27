
import pandas as pd
from datetime import timedelta
from pathlib import Path

def run_match_report():
    symbol = "ADAUSDT"
    print(f"💎 FINAL RECONCILIATION: {symbol}")
    
    path = Path(f"coin_cells/{symbol}/data/history_15m.parquet")
    if not path.exists(): return
    df = pd.read_parquet(path)
    
    if 'open_time' not in df.columns:
        if 'timestamp' in df.columns:
            df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    else:
        df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.sort_values('open_time').reset_index(drop=True)
    
    # 1. Broad Scan: >30% Gain within 8 Hours (32 bars) - Low Latency Definition
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=32) 
    df['future_max'] = df['close'].rolling(window=indexer).max()
    df['gain_pot'] = (df['future_max'] - df['close']) / df['close'] * 100
    
    candidates = df[df['gain_pot'] > 30.0].index
    
    rallies = []
    last_idx = -100
    
    for idx in candidates:
        if idx - last_idx < 32: continue # Dedupe same day waves
        last_idx = idx
        
        row = df.loc[idx]
        
        # Capture Start Time (UTC)
        start_time_utc = row['open_time']
        
        # Convert to User Time (TR = UTC+3)
        start_time_tr = start_time_utc + timedelta(hours=3)
        
        rallies.append({
            'utc': start_time_utc,
            'tr': start_time_tr,
            'gain': row['gain_pot']
        })
        
    # User's Know List (Approximate TR Times)
    user_list_tr = [
        pd.to_datetime("2025-10-11 00:15:00"), # 10 Oct 21:15 UTC
        pd.to_datetime("2025-03-02 09:15:00"), # 02 Mar 06:15 UTC
        pd.to_datetime("2025-03-02 18:15:00"), # 02 Mar 15:15 UTC
        pd.to_datetime("2024-11-22 13:00:00"), 
        pd.to_datetime("2024-11-09 18:00:00")
    ]
    
    print("\n" + "="*80)
    print(f"{'USER TIME (TR)':<22} | {'UTC TIME':<20} | {'GAIN %':<8} | {'STATUS'}")
    print("-" * 80)
    
    for r in rallies:
        # Check match
        match_status = "✨ NEW DISCOVERY"
        
        # Simple proximity check (within 2 hours)
        for u in user_list_tr:
            diff = abs((r['tr'] - u).total_seconds() / 3600)
            if diff < 2.5:
                match_status = "✅ YOUR FIND"
                break
                
        print(f"{str(r['tr']):<22} | {str(r['utc']):<20} | {r['gain']:<6.1f}%   | {match_status}")
        
    print("-" * 80)

if __name__ == "__main__":
    run_match_report()
