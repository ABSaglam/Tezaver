import pandas as pd
import numpy as np
import json
import os
import math
from scipy.stats import linregress

# CONFIG
RAW_RALLIES_FILE = "v7_raw_rallies.json" # Still useful for raw event timestamps
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_PROFILE = "v7_coin_specific_dna.json"
TRAIN_END_DATE = "2025-12-31"

def calculate_aesthetics(price_series, rsi_series):
    # Smoothness (Last 12 bars close)
    if len(price_series) < 5: return 0, 0
    y = np.arange(len(price_series))
    slope, intercept, r_value, p_value, std_err = linregress(y, price_series)
    smooth = r_value ** 2
    
    # RSI Angle (Last 3 bars)
    if len(rsi_series) < 3: return smooth, 0
    y_rsi = rsi_series[-3:]
    x_rsi = np.arange(3)
    slope_r, _, _, _, _ = linregress(x_rsi, y_rsi)
    angle = math.degrees(math.atan(slope_r))
    
    return smooth, angle

def run_specific_training():
    print(f"🧠 V7: Learning Coin-Specific Souls (Train until {TRAIN_END_DATE})...")
    
    # Load raw rallies to know WHERE to look, but we need to verify them per coin
    if os.path.exists(RAW_RALLIES_FILE):
        with open(RAW_RALLIES_FILE, 'r') as f:
            raw_data = json.load(f)
    else:
        raw_data = {}

    coin_dna = {}
    
    coins = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    for idx, coin in enumerate(coins):
        # Default Profile
        coin_dna[coin] = {
            "SUP": {"angle_min": 65, "smooth_min": 0.0}, # Fallbacks
            "success_samples": 0
        }
        
        path = f"{COIN_CELLS_DIR}/{coin}/data/history_15m.parquet"
        if not os.path.exists(path): continue
        
        try:
            df = pd.read_parquet(path)
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df.sort_index(inplace=True)
            
            # TRAINING RANGE ONLY
            train_df = df[df.index <= TRAIN_END_DATE]
            if train_df.empty: continue
            
            # Indicators
            delta = train_df['close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean().replace(0, 0.001)
            train_df['rsi'] = 100 - (100 / (1 + (gain / loss)))
            
            # Collect Successful Rallies for THIS coin
            # We use the raw events but re-verify locally
            events = raw_data.get(coin, [])
            
            angles = []
            smooths = []
            fail_angles = []
            fail_smooths = []
            
            for e in events:
                start_ts = pd.to_datetime(e['start_ts'])
                if start_ts > pd.Timestamp(TRAIN_END_DATE): continue # Skip 2026 events
                if e['gain_pct'] < 5.0: continue # Skip Failures (We only want the soul of Winners)
                
                # Get Context: 12 bars before start
                loc_idx = train_df.index.get_indexer([start_ts], method='nearest')[0]
                if loc_idx < 15: continue
                
                context_price = train_df['close'].iloc[loc_idx-12 : loc_idx].values
                context_rsi = train_df['rsi'].iloc[loc_idx-3 : loc_idx].values
                
                sm, ang = calculate_aesthetics(context_price, context_rsi)
                
                # Filter: Only consider "Supernova-ish" behavior locally
                if ang > 45: 
                    if e['gain_pct'] >= 5.0:
                        angles.append(ang)
                        smooths.append(sm)
                    else:
                        # This is a FAILURE (Fake Pump)
                        fail_angles.append(ang)
                        fail_smooths.append(sm)
            
            # --- SUCCESS PROFILE (The Goal) ---
            if len(angles) >= 3:
                avg_ang = np.mean(angles)
                std_ang = np.std(angles)
                # STRICTER: Min 70 degrees, and aim for the Average (don't lower bar)
                target_ang = max(70, avg_ang) 
                
                avg_sm = np.mean(smooths)
                
                coin_dna[coin]["SUP"] = {
                    "angle_min": round(target_ang, 1),
                    "smooth_min": round(max(0.1, avg_sm - 0.2), 2), # Min smooth 0.1
                    "centroid_ang": round(avg_ang, 1), 
                    "centroid_sm": round(avg_sm, 2)
                }
                coin_dna[coin]["success_samples"] = len(angles)
            
            # --- FAILURE PROFILE (The Trap) ---
            if len(fail_angles) >= 3:
                 coin_dna[coin]["FAIL"] = {
                    "centroid_ang": round(np.mean(fail_angles), 1),
                    "centroid_sm": round(np.mean(fail_smooths), 2)
                }
            else:
                # DEFAULT TRAP: If no specific failure history, assume anything 
                # with High Angle but Low Smoothness is a trap.
                # Or use a generic "Fake Pump" profile: 65deg, 0.2 smooth
                coin_dna[coin]["FAIL"] = {
                    "centroid_ang": 65.0,
                    "centroid_sm": 0.20
                }
                
        except Exception:
            pass
            
        print(f"Training {idx+1}/{len(coins)}: {coin} -> DNA: >{coin_dna[coin]['SUP']['angle_min']}°", end='\r')

    with open(OUTPUT_PROFILE, 'w') as f:
        json.dump(coin_dna, f, indent=2)
        
    print(f"\n✅ Training Complete. Saved specific souls -> {OUTPUT_PROFILE}")

if __name__ == "__main__":
    run_specific_training()
