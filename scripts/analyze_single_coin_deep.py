
import pandas as pd
import numpy as np
import glob
import random
from pathlib import Path
from tezaver.core import coin_cell_paths

def analyze_single_coin_deep():
    print("🎲 Selecting a random coin for Deep Scan...")
    
    # 1. Find all coins with history
    files = glob.glob("coin_cells/*/data/history_15m.parquet")
    if not files:
        # Fallback
        files = glob.glob("/Users/alisaglam/TezaverMac/coin_cells/*/data/history_15m.parquet")
        
    if not files:
        print("❌ No history data found.")
        return

    # Pick Random
    target_file = random.choice(files)
    symbol = Path(target_file).parent.parent.name
    print(f"🎯 Selected Subject: {symbol}")
    
    # 2. Load Data
    try:
        df = pd.read_parquet(target_file)
    except Exception as e:
        print(f"Error reading file: {e}")
        return
        
    # Ensure correct datetime conversion (Robust Mix)
    if 'open_time' in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df['open_time']):
            df['timestamp'] = df['open_time']
        else:
             sample = df['open_time'].iloc[0]
             if sample > 1e11:
                 df['timestamp'] = pd.to_datetime(df['open_time'], unit='ms')
             else:
                 df['timestamp'] = pd.to_datetime(df['open_time'], unit='s')
    elif 'timestamp' in df.columns:
         if pd.api.types.is_numeric_dtype(df['timestamp']):
             sample = df['timestamp'].iloc[0]
             if sample > 1e11:
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
             else:
                 df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
         else:
             df['timestamp'] = pd.to_datetime(df['timestamp'])
    else:
         df['timestamp'] = pd.to_datetime(df.index)
         
    # Sort
    df = df.sort_values('timestamp').reset_index(drop=True)
    if df['timestamp'].dt.tz is not None:
         df['timestamp'] = df['timestamp'].dt.tz_localize(None)

    print(f"📅 Data Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"📊 Total Candles: {len(df)}")
    
    # 3. Detect Rallies (>10%)
    print("\n🔍 Scanning for >10% Rallies (Lookahead 24h)...")
    
    close = df['close'].values
    high = df['high'].values
    timestamps = df['timestamp']
    n = len(df)
    lookahead = 96 # 24h
    min_gain = 0.10
    
    rallies = []
    i = 0
    
    while i < n - lookahead:
        current_close = close[i]
        
        # Check future max
        window_high = np.max(high[i+1 : i+1+lookahead])
        gain = (window_high - current_close) / current_close
        
        if gain >= min_gain:
            # RALLY FOUND!
            # Find peak index
            peak_offset = np.argmax(high[i+1 : i+1+lookahead]) + 1
            peak_time = timestamps[i+peak_offset]
            
            # Context Metrics (Entry Conditions)
            # RSI just before entry?
            # Need previous 14 bars
            rsi_val = np.nan
            if i > 14:
                # Calc RSI manually for speed on this slice
                slice_c = pd.Series(close[i-14:i+1])
                delta = slice_c.diff()
                g = delta.where(delta>0, 0).mean() # approximate for speed
                l = -delta.where(delta<0, 0).mean()
                if l != 0:
                    rs = g/l
                    rsi_val = 100 - (100/(1+rs))
                else:
                    rsi_val = 100
            
            rallies.append({
                'date': timestamps[i],
                'gain_pct': gain * 100,
                'peak_time': peak_time,
                'duration_bars': peak_offset,
                'entry_rsi': rsi_val
            })
            
            # Skip past this rally to find the next DISTINCT one
            # Jump to Peak + Cool Down (20 bars)
            i += peak_offset + 20
        else:
            i += 1
            
    if not rallies:
        print("No >10% rallies found.")
        return
        
    df_res = pd.DataFrame(rallies)
    df_res = df_res.sort_values('gain_pct', ascending=False)
    
    print(f"\n🏆 Found {len(df_res)} Major Rallies (>10%) for {symbol}")
    print("-" * 60)
    print(f"{'Date':<20} | {'Gain':<8} | {'Dur(h)':<6} | {'Entry RSI':<9}")
    print("-" * 60)
    
    for _, row in df_res.head(20).iterrows():
        dur_h = row['duration_bars'] * 0.25
        rsi_str = f"{row['entry_rsi']:.1f}" if not pd.isna(row['entry_rsi']) else "N/A"
        print(f"{str(row['date']):<20} | {row['gain_pct']:.1f}%    | {dur_h:<6.1f} | {rsi_str:<9}")
        
    print("\n------------------------------------------------------------")
    print(f"💡 Average Gain: {df_res['gain_pct'].mean():.1f}%")
    print(f"💡 Average duration to peak: {(df_res['duration_bars'].mean()*0.25):.1f} hours")


if __name__ == "__main__":
    analyze_single_coin_deep()
