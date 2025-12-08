
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import glob
from pathlib import Path
from tezaver.core import coin_cell_paths

def visualize_bridges_to_peak():
    print("🗺️ Mapping the 'Roads to Glory'...")
    
    # 1. Load Rally Data
    files = glob.glob("library/fast15_rallies/*/fast15_rallies.parquet")
    all_events = []
    for f in files:
        try:
            df = pd.read_parquet(f)
            df['symbol'] = Path(f).parent.name
            # Filter for decent size rallies only
            df = df[df['future_max_gain_pct'] > 0.15] 
            all_events.append(df)
        except:
            continue
            
    if not all_events:
        print("No rallies found.")
        return
        
    df_rallies = pd.concat(all_events).sort_values('future_max_gain_pct', ascending=False).head(50)
    
    # 2. Extract Paths
    price_paths = []
    rsi_paths = []
    
    lookback = 96 # 24 Hours
    
    for _, row in df_rallies.iterrows():
        symbol = row['symbol']
        # The event_time is the "Start". The Peak is 'bars_to_peak' later.
        start_time = row['event_time']
        bars_to_peak = int(row['bars_to_peak'])
        
        # Load History
        f = coin_cell_paths.get_history_file(symbol, "15m")
        if not f.exists(): continue
        try:
            df_hist = pd.read_parquet(f)
        except: continue
        
        # Smart Datetime (Robust)
        if 'open_time' in df_hist.columns:
            if pd.api.types.is_datetime64_any_dtype(df_hist['open_time']):
                df_hist['timestamp'] = df_hist['open_time']
            else:
                 sample = df_hist['open_time'].iloc[0]
                 if sample > 1e11:
                     df_hist['timestamp'] = pd.to_datetime(df_hist['open_time'], unit='ms')
                 else:
                     df_hist['timestamp'] = pd.to_datetime(df_hist['open_time'], unit='s')
        elif 'timestamp' in df_hist.columns:
             if pd.api.types.is_numeric_dtype(df_hist['timestamp']):
                 sample = df_hist['timestamp'].iloc[0]
                 if sample > 1e11:
                     df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'], unit='ms')
                 else:
                     df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'], unit='s')
             else:
                 df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'])
        else:
             df_hist['timestamp'] = pd.to_datetime(df_hist.index)

        # Sort
        df_hist = df_hist.sort_values('timestamp').reset_index(drop=True)
        if df_hist['timestamp'].dt.tz is not None:
             df_hist['timestamp'] = df_hist['timestamp'].dt.tz_localize(None)

        # Find Index of START
        target_time = start_time.replace(tzinfo=None)
        
        # Binary search
        ts_values = df_hist['timestamp'].values
        target_ts64 = np.datetime64(target_time)
        idx = np.searchsorted(ts_values, target_ts64)
        
        if idx >= len(ts_values):
            idx = len(ts_values) - 1
            
        found_ts = pd.to_datetime(ts_values[idx])
        diff = abs((found_ts - target_time).total_seconds())
        
        if diff > 3600:
             # Try previous
             if idx > 0:
                 found_tsp = pd.to_datetime(ts_values[idx-1])
                 diffp = abs((found_tsp - target_time).total_seconds())
                 if diffp < diff: 
                     idx = idx - 1
                     diff = diffp
             
             if diff > 3600:
                 # print(f"Skipping path for {symbol}: Time diff {diff}s too big")
                 continue
                 
        # The PEAK is at `idx + bars_to_peak`
        peak_idx = idx + bars_to_peak
        
        # We want the road leading TO the peak. Let's say Peak - 96 bars.
        path_start = max(0, peak_idx - lookback)
        path_end = peak_idx
        
        chunk = df_hist.iloc[path_start:path_end+1].copy()
        if len(chunk) < 20: continue # allow shorter but need some
        
        # Normalize Price (0 to 1)
        prices = chunk['close'].values
        p_min = np.min(prices)
        p_max = np.max(prices)
        if p_max == p_min: continue
        norm_price = (prices - p_min) / (p_max - p_min)
        
        # Calculate RSI if needed
        norm_rsi = None # skip RSI for now to simplify plotting logic 
        # (or re-implement if requested, but user asked for "roads")
            
        price_paths.append(norm_price)
        # rsi_paths.append(norm_rsi)


    # 3. Plotting
    print(f"Plotting {len(price_paths)} roads...")
    
    if not price_paths:
        print("No valid paths found.")
        return

    # Ensure equal length (97 points: -96 to 0)
    expected_len = lookback + 1
    clean_paths = []
    
    for p in price_paths:
        if len(p) == expected_len:
            clean_paths.append(p)
        elif len(p) > expected_len:
            clean_paths.append(p[-expected_len:])
        else:
            # Pad with first value
            pad = np.full(expected_len - len(p), p[0])
            clean_paths.append(np.concatenate([pad, p]))
            
    price_paths = np.array(clean_paths)
    # Remove any rows with NaN
    mask = ~np.isnan(price_paths).any(axis=1)
    price_paths = price_paths[mask]
    
    if len(price_paths) == 0:
        print("All paths contained NaN.")
        return
        
    avg_path = np.nanmean(price_paths, axis=0) # Use nanmean just in case
    
    # Replace NaNs in avg_path if any (shouldn't be)
    avg_path = np.nan_to_num(avg_path, nan=0.5)

    fig = go.Figure()
    
    # Add all price paths as faint lines
    x_axis = list(range(-lookback, 1)) # -96 to 0 (Peak)
    
    for p in price_paths:
        fig.add_trace(go.Scatter(
            x=x_axis, y=p, 
            mode='lines', 
            line=dict(color='rgba(0, 255, 255, 0.1)', width=1), # More transparent
            showlegend=False,
            hoverinfo='skip'
        ))
        
    # Add Average Road (The Golden Highway)
    avg_path = np.mean(price_paths, axis=0)
    fig.add_trace(go.Scatter(
        x=x_axis, y=avg_path,
        mode='lines',
        name='The Golden Path (Avg)',
        line=dict(color='white', width=4)
    ))

    fig.update_layout(
        title="Rally Roads: The 24 Hours Leading to the Peak",
        xaxis_title="Bars Before Peak (0 = Peak)",
        yaxis_title="Normalized Progress (0-1)",
        template="plotly_dark",
        width=1000, height=600
    )
    
    output_path = "rally_roads_map.html"
    fig.write_html(output_path)
    print(f"✅ Map created: {output_path}")
    
    # Calculate key stats of the road
    # e.g. at -40 bars (10 hours before peak), where was the average?
    # List indices correspond to x_axis. -96 is index 0. -40 is index 56. 0 is index 96.
    
    print("\n--- ROAD SIGNS ---")
    val_at_start = avg_path[0]
    val_at_mid = avg_path[lookback // 2]
    val_at_peak = avg_path[-1]
    
    print(f"📍 Start of Journey (-24h): {val_at_start:.2f}")
    print(f"📍 Halfway Point (-12h):   {val_at_mid:.2f}")
    print(f"📍 The Peak (0h):          {val_at_peak:.2f}")
    
    if val_at_mid < val_at_start:
        print("📉 Insight: The road typically DIPS before climbing (The 'V' Shape).")
    else:
        print("📈 Insight: The road is a steady climb.")

if __name__ == "__main__":
    visualize_bridges_to_peak()
