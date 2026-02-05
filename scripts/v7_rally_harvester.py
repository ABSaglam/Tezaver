import pandas as pd
import numpy as np
import os
import json
from datetime import timedelta

# CONFIG
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_FILE = "v7_raw_rallies.json"
MIN_GAIN_PCT = 10.0  # Capture anything > 10% as a potential rally candidate
SCAN_WINDOW_HOURS = 24

def run_harvest():
    print("🚜 V7: Grand Harvest Started...")
    
    coins = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    print(f"🎯 Target: {len(coins)} Coins")
    
    all_rallies = {}
    total_events = 0
    
    for idx, coin in enumerate(coins):
        path_15m = f"{COIN_CELLS_DIR}/{coin}/data/history_15m.parquet"
        if not os.path.exists(path_15m): continue
        
        try:
            df = pd.read_parquet(path_15m)
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df.sort_index(inplace=True)
            
            # Fast Vectorized Rolling Max to find rallies
            # We look for: (High in next 24h - Current Open) / Current Open > 10%
            
            # Resample to 1H for faster initial scan? No, keep 15m for precision.
            # Rolling window size for 24h = 24 * 4 = 96 bars
            indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=96)
            
            # Future Max High
            df['future_high'] = df['high'].rolling(window=indexer).max()
            
            # Gain Percentage
            df['max_gain'] = ((df['future_high'] - df['open']) / df['open']) * 100
            
            # Filter Candidates
            candidates = df[df['max_gain'] >= MIN_GAIN_PCT]
            
            # Debounce: If we have consecutive triggers, group them into one event.
            # We want the START of the rally.
            
            coin_events = []
            
            if not candidates.empty:
                # Iterate candidates and group
                last_event_end = pd.Timestamp.min
                
                for ts, row in candidates.iterrows():
                    if ts < last_event_end: continue
                    
                    # New Event Found
                    # Find the exact peak within next 24h
                    scan_end = ts + timedelta(hours=24)
                    window = df[(df.index >= ts) & (df.index <= scan_end)]
                    
                    if window.empty: continue
                    
                    peak_ts = window['high'].idxmax()
                    peak_val = window.loc[peak_ts, 'high']
                    gain_real = ((peak_val - row['open']) / row['open']) * 100
                    
                    # Save Event
                    event = {
                        "start_ts": ts.strftime("%Y-%m-%d %H:%M:%S"),
                        "peak_ts": peak_ts.strftime("%Y-%m-%d %H:%M:%S"),
                        "start_price": float(row['open']),
                        "peak_price": float(peak_val),
                        "gain_pct": float(gain_real),
                        "duration_bars": int((peak_ts - ts).seconds / 900)
                    }
                    coin_events.append(event)
                    total_events += 1
                    
                    # Advance skip pointer
                    last_event_end = peak_ts + timedelta(hours=4) # Cooldown
            
            if coin_events:
                all_rallies[coin] = coin_events
                
        except Exception as e:
            print(f"❌ Error {coin}: {e}")
        
        print(f"Scanning {idx+1}/{len(coins)}: {coin} -> {len(coin_events if 'coin_events' in locals() else [])} Rallies Found", end='\r')

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_rallies, f, indent=2)
        
    print(f"\n✅ Harvest Complete. Collected {total_events} rallies across {len(all_rallies)} coins.")
    print(f"📦 Saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    run_harvest()
