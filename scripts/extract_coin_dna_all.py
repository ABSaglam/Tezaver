
import pandas as pd
import numpy as np
import glob
from pathlib import Path

def extract_coin_dna():
    print("🧬 Creating 'Special Recipes' for each coin (DNA Extraction)...")
    
    # 1. Find all coins
    files = glob.glob("coin_cells/*/data/history_15m.parquet")
    if not files:
        files = glob.glob("/Users/alisaglam/TezaverMac/coin_cells/*/data/history_15m.parquet")
    
    if not files:
        print("❌ No data found.")
        return

    dna_registry = []

    for f in files:
        symbol = Path(f).parent.parent.name
        # print(f"decoding {symbol}...")
        
        try:
            df = pd.read_parquet(f)
        except: continue
        
        # Datetime fix
        if 'open_time' in df.columns:
             if 'timestamp' not in df.columns:
                # auto detect unit
                sample = df['open_time'].iloc[0] if len(df) > 0 else 0
                unit = 'ms' if sample > 1e11 else 's'
                df['timestamp'] = pd.to_datetime(df['open_time'], unit=unit)
        elif 'timestamp' in df.columns:
             if pd.api.types.is_numeric_dtype(df['timestamp']):
                 sample = df['timestamp'].iloc[0] if len(df) > 0 else 0
                 unit = 'ms' if sample > 1e11 else 's'
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit=unit)
        else:
            df['timestamp'] = pd.to_datetime(df.index)

        df = df.sort_values('timestamp').reset_index(drop=True)
        if len(df) < 500: continue
        
        # Scan for >10% Rallies
        close = df['close'].values
        high = df['high'].values
        n = len(df)
        lookahead = 96 # 24h
        
        winning_entries = [] # Store RSIs
        
        # Calculate RSI for whole series for speed
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        rsi_vals = df['rsi'].values
        
        i = 14
        while i < n - lookahead:
            current_close = close[i]
            if current_close <= 0: 
                i+=1; continue
                
            window_high = np.max(high[i+1 : i+1+lookahead])
            gain_pct = (window_high - current_close) / current_close
            
            if gain_pct >= 0.10: # >10% Gain
                # Capture DNA
                entry_rsi = rsi_vals[i]
                
                # Check previous trend (was it accumulating?)
                # 4-hour slope? 
                
                if not np.isnan(entry_rsi):
                    winning_entries.append(entry_rsi)
                
                # Skip forward to avoid overlap
                peak_idx = np.argmax(high[i+1 : i+1+lookahead]) + 1
                i += peak_idx + 20
            else:
                i += 1
                
        if winning_entries:
            avg_rsi = np.mean(winning_entries)
            # determine recipe
            if avg_rsi < 30:
                recipe = "Deep Diver 🤿 (Buy < 30)"
            elif avg_rsi < 45:
                recipe = "Trend Surfer 🏄 (Buy 30-45)"
            else:
                recipe = "Momentum Rider 🚀 (Buy > 45)"
                
            dna_registry.append({
                'Symbol': symbol,
                'Rally_Count': len(winning_entries),
                'Sweet_Spot_RSI': round(avg_rsi, 1),
                'Recipe': recipe
            })

    # Sort and Report
    if not dna_registry:
        print("No >10% rallies found across the board.")
        return
        
    df_dna = pd.DataFrame(dna_registry).sort_values('Sweet_Spot_RSI')
    
    print(f"\n🧬 COIN DNA REGISTRY ({len(df_dna)} Coins Analyzed)")
    print("-" * 75)
    print(df_dna.to_string(index=False))
    print("-" * 75)
    print("Insight: Use these 'Sweet Spot' RSI values as specific triggers for each coin.")

if __name__ == "__main__":
    extract_coin_dna()
