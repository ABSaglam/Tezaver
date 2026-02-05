import pandas as pd
import numpy as np
import json
import os
import math
from scipy.stats import linregress
from datetime import datetime

# CONFIG
PROFILE_FILE = "v7_archetype_dna_profiles.json"
COIN_CELLS_DIR = "/Users/alisaglam/TezaverMac/coin_cells"
OUTPUT_REPORT = "v7_harmony_report_feb_2026.md"
START_DATE = "2026-01-01"
END_DATE = "2026-02-02"

def calculate_smoothness(prices):
    if len(prices) < 5: return 0
    y = np.array(prices)
    x = np.arange(len(y))
    slope, intercept, r_value, p_value, std_err = linregress(x, y)
    return r_value ** 2

def calculate_rsi_angle(rsi_series):
    if len(rsi_series) < 3: return 0
    y = rsi_series[-3:]
    x = np.arange(3)
    slope, _, _, _, _ = linregress(x, y)
    return math.degrees(math.atan(slope))

def run_scanner():
    print("🎹 V7: Harmony Scanner Started...")
    
    with open(PROFILE_FILE, 'r') as f:
        profiles = json.load(f)
        
    coins = [d for d in os.listdir(COIN_CELLS_DIR) if os.path.isdir(os.path.join(COIN_CELLS_DIR, d))]
    
    report_lines = []
    
    for idx, coin in enumerate(coins):
        path = f"{COIN_CELLS_DIR}/{coin}/data/history_15m.parquet"
        if not os.path.exists(path): continue
        
        try:
            df = pd.read_parquet(path)
            df['dt'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('dt', inplace=True)
            df = df.sort_index()
            
            mask = (df.index >= START_DATE) & (df.index <= END_DATE)
            df = df[mask]
            if df.empty: continue

            # Calc Indicators
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
            loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean().replace(0, 0.001)
            df['rsi'] = 100 - (100 / (1 + (gain / loss)))
            
            # Scan Loop
            for i in range(20, len(df)):
                row = df.iloc[i]
                
                # Check Aesthetics (Last 12 bars context)
                context = df.iloc[i-12 : i]
                current_smooth = calculate_smoothness(context['close'].values)
                current_angle = calculate_rsi_angle(df['rsi'].iloc[i-3:i].values)
                
                # Check for SUPERNOVA Match
                # Ideal: Low Smoothness (Chaos) -> High Angle (Explosion)
                # Profile says Avg Smoothness 0.013. 
                # Our logic: heavily penalize if smoothness is too high (boring market) 
                # UNLESS it is a Grind.
                
                # Dynamic Thresholds
                is_supernova_candidate = (current_angle > 60) # Must have vertical pop
                is_grind_candidate = (current_smooth > 0.8) and (current_angle > 45) # Orderly climb
                
                signal_type = None
                
                if is_supernova_candidate:
                    signal_type = "SUPERNOVA"
                elif is_grind_candidate:
                    signal_type = "GRIND"
                    
                if signal_type:
                    # Capture Signal
                    ts_str = df.index[i].strftime("%Y-%m-%d %H:%M")
                    report_lines.append(f"| {ts_str} | {coin} | {signal_type} | Smooth: {current_smooth:.2f} | Ang: {current_angle:.0f}° | Price: {row['close']} |")
                    
        except Exception:
            continue
            
        print(f"Scanning {idx}/{len(coins)}...", end='\r')

    # Save
    with open(OUTPUT_REPORT, 'w') as f:
        f.write("# V7 Harmony Report (Aesthetic Detection)\n")
        f.write("| Time | Symbol | Archetype | Smoothness | Angle | Price |\n")
        f.write("|---|---|---|---|---|---|\n")
        for line in report_lines:
            f.write(line + "\n")
            
    print(f"\n✅ Scan Complete. Signals: {len(report_lines)}")

if __name__ == "__main__":
    run_scanner()
