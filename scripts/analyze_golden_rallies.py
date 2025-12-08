
import pandas as pd
import numpy as np
import glob
from pathlib import Path
from tezaver.core import coin_cell_paths
# from tezaver.data.history_service import load_history_data
from tezaver.core.config import DEFAULT_CHART_TIMEFRAME

def analyze_golden_rallies():
    print("🔍 Searching for 'Golden Rallies' (Top 50 Winners)...")
    
    # 1. Gather all events
    files = glob.glob("library/fast15_rallies/*/fast15_rallies.parquet")
    if not files:
        print("❌ No rally data found. Run Fast15 scan first.")
        return

    all_events = []
    for f in files:
        try:
            df = pd.read_parquet(f)
            df['symbol'] = Path(f).parent.name
            all_events.append(df)
        except Exception as e:
            print(f"Error reading {f}: {e}")
            
    if not all_events:
        print("❌ No events found.")
        return
        
    df_all = pd.concat(all_events)
    
    # 2. Filter for Giants (Top 50 by % Gain)
    # Filter out insane outliers > 500% (likely data glitches or wicks) if any, but let's keep them for now.
    df_giants = df_all.sort_values('future_max_gain_pct', ascending=False).head(50)
    
    print(f"🏆 Found {len(df_giants)} Golden Rallies.")
    print(f"   Min Gain: {df_giants['future_max_gain_pct'].min()*100:.1f}%")
    print(f"   Max Gain: {df_giants['future_max_gain_pct'].max()*100:.1f}%")
    
    # 3. Analyze "Pre-Rally Context" (Last 40 Bars before Trigger)
    print("\n🔬 Deep Dive: Analyzing the 40 bars BEFORE the explosion...")
    
    signatures = []
    
    for idx, row in df_giants.iterrows():
        symbol = row['symbol']
        event_time = row['event_time']
        gain = row['future_max_gain_pct']
        


        # Direct Load
        history_file = coin_cell_paths.get_history_file(symbol, "15m")
        if not history_file.exists():
            print(f"Skipping {symbol}: History file not found at {history_file}")
            continue
            
        try:
            df_hist = pd.read_parquet(history_file)
        except Exception as e:
            print(f"Skipping {symbol}: Read Parquet failed: {e}")
            continue
            
        # DEBUG
        print(f"Processing {symbol} at {event_time}")
             
        
        # Ensure datetime with smart inference
        if 'open_time' in df_hist.columns:
            # Check dtype first
            if pd.api.types.is_datetime64_any_dtype(df_hist['open_time']):
                df_hist['timestamp'] = df_hist['open_time']
            else:
                # Check magnitude
                sample = df_hist['open_time'].iloc[0]
                if sample > 1e11: # Likely MS (13 digits)
                    df_hist['timestamp'] = pd.to_datetime(df_hist['open_time'], unit='ms')
                else: # Likely Seconds (10 digits)
                    df_hist['timestamp'] = pd.to_datetime(df_hist['open_time'], unit='s')
                    
        elif 'timestamp' in df_hist.columns:
            # Same check for 'timestamp' col if it exists
            if pd.api.types.is_numeric_dtype(df_hist['timestamp']):
                 sample = df_hist['timestamp'].iloc[0]
                 if sample > 1e11:
                     df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'], unit='ms')
                 else:
                     df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'], unit='s')
            else:
                df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'])
        else:
             df_hist['timestamp'] =  pd.to_datetime(df_hist.index)
        
        # Sort
        df_hist = df_hist.sort_values('timestamp').reset_index(drop=True)
        # Ensure naive
        if df_hist['timestamp'].dt.tz is not None:
             df_hist['timestamp'] = df_hist['timestamp'].dt.tz_localize(None)
        
        
        # Match time using searchsorted (Find closest index)
        # Event time from parquet is likely naive or UTC
        target_time = event_time.replace(tzinfo=None) # Restore definition
        
        # Convert to numpy array for speed
        ts_array = df_hist['timestamp'].values
        target_ts64 = np.datetime64(target_time)
        
        # Find insertion point
        idx = np.searchsorted(ts_array, target_ts64)
        
        # Check if valid
        if idx >= len(ts_array):
            idx = len(ts_array) - 1
        
        # Check diff
        found_ts = pd.to_datetime(ts_array[idx])
        diff = abs((found_ts - target_time).total_seconds())
        
        if diff > 3600: # Allow 1 hour slack (maybe 1h/4h confusion)
            # Try previous index
            if idx > 0:
                found_ts_prev = pd.to_datetime(ts_array[idx-1])
                diff_prev = abs((found_ts_prev - target_time).total_seconds())
                if diff_prev < diff:
                    idx = idx - 1
                    diff = diff_prev
            
            if diff > 3600:
                print(f"Skipping {symbol} {event_time}: Closest time {found_ts} diff {diff:.0f}s too large.")
                continue
                
        event_idx = idx
        print(f"Matched {symbol}: Target {target_time} -> Found {ts_array[idx]} (Diff {diff:.1f}s)")
        
        # SLICE: 40 bars before

        # SLICE: 40 bars before
        # We want the window leading UP TO the event
        start_idx = max(0, event_idx - 40)
        # We stop AT (or right before) the event to simulate "Pre-Trade" view
        df_window = df_hist.iloc[start_idx:event_idx].copy()

        
        if df_window.empty:
            print(f"Skipping {symbol}: Window empty (Start {start_idx} End {event_idx})")
            continue
            
        # --- CALCULATE SIGNATURE METRICS ---
        
        # 1. RSI (Calculate on fly if missing)
        try:
            if 'rsi' not in df_window.columns:
                delta = df_window['close'].diff()
                gain_s = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss_s = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain_s / loss_s
                df_window['rsi'] = 100 - (100 / (1 + rs))
            
            # Signature:
            min_rsi = df_window['rsi'].min()
            last_rsi = df_window['rsi'].iloc[-1]
            
            # 2. Volume Trend
            avg_vol = df_window['volume'].mean()
            last_vol = df_window['volume'].iloc[-1]
            vol_surge = last_vol / avg_vol if avg_vol > 0 else 0
            
            # 3. Price Change in Pre-Window (Was it dumping or accumulating?)
            price_start = df_window['close'].iloc[0]
            price_end = df_window['close'].iloc[-1]
            pre_change_pct = (price_end - price_start) / price_start * 100
            
            signatures.append({
                'symbol': symbol,
                'gain_pct': gain * 100,
                'pre_rsi_min': min_rsi,
                'pre_rsi_last': last_rsi,
                'pre_vol_surge': vol_surge,
                'pre_price_move': pre_change_pct,
                'narrative': row.get('scenario_label', 'Unknown')
            })
            print(f" -> ADDED SIGNATURE for {symbol}")
        except Exception as e:
            print(f"Error calculating metrics for {symbol}: {e}")
            continue

    if not signatures:
        print("❌ No signatures extracted. Check debug logs above.")
        return

    df_sig = pd.DataFrame(signatures)
    
    print("\n--- GOLDEN RALLY DNA REPORT ---")
    print(df_sig.describe().round(2))
    
    print("\n--- SAMPLE WINNERS ---")
    print(df_sig[['symbol', 'gain_pct', 'pre_rsi_min', 'pre_vol_surge', 'pre_price_move', 'narrative']].head(10).to_string())
    
    print("\n-------------------------------")
    print("Insight Generator:")
    avg_rsi_min = df_sig['pre_rsi_min'].mean()
    print(f"💡 On average, before a massive rally, RSI dropped to {avg_rsi_min:.1f} in the last 40 bars.")
    
    accumulators = len(df_sig[ (df_sig['pre_price_move'] > -5) & (df_sig['pre_price_move'] < 5) ])
    print(f"💡 {accumulators}/{len(df_sig)} of giants were 'Accumulating' (Flat Price) before the pump.")

if __name__ == "__main__":
    analyze_golden_rallies()
