
import pandas as pd
import numpy as np
from pathlib import Path
import sys

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def run_autopsy(symbol="ADAUSDT", target_time_str="2023-12-08 16:00:00"):
    path = Path(f"coin_cells/{symbol}/data/history_15m.parquet")
    if not path.exists():
        print(f"File not found: {path}")
        return

    print("LOADING DATA...")
    df = pd.read_parquet(path)
    
    # Normalize Time
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
        
    df = df.sort_values('open_time').reset_index(drop=True)

    # Calculate Indicators Globally first (for EMA/RSI accuracy)
    print("CALCULATING INDICATORS...")
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['rsi_ema'] = df['rsi'].ewm(span=14, adjust=False).mean()
    df['rsi_delta'] = df['rsi'] - df['rsi_ema']
    df['ma50'] = df['close'].rolling(50).mean()
    df['ma200'] = df['close'].rolling(200).mean()
    df['vol_ma50'] = df['volume'].rolling(50).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma50']
    
    rolling_mean = df['close'].rolling(20).mean()
    rolling_std = df['close'].rolling(20).std()
    df['bb_width'] = (rolling_std * 2) / rolling_mean * 100

    # Locate Target
    target_ts = pd.to_datetime(target_time_str)
    # tz naive handling
    if df['open_time'].dt.tz is not None and target_ts.tz is None:
        target_ts = target_ts.tz_localize('UTC')
        
    mask = df['open_time'] == target_ts
    if not mask.any():
        print(f"Target Time {target_ts} NOT FOUND in data.")
        # Attempt close match
        closest_idx = (df['open_time'] - target_ts).abs().idxmin()
        actual_time = df.loc[closest_idx, 'open_time']
        print(f"Closest match: {actual_time}")
        idx = closest_idx
    else:
        idx = df.index[mask][0]
        
    print(f"\nAUTOPSY TARGET: {df.loc[idx, 'open_time']} (Price: {df.loc[idx, 'close']})")
    
    # Slice Context (User wants to know 'what happened before')
    # Let's look at T-10 bars to T=0
    context = df.iloc[idx-10 : idx+1].copy()
    
    print("\n" + "="*50)
    print("🕵️‍♂️ AUTOPSY REPORT: THE PREPARATION PHASE")
    print("="*50)
    
    # 1. RSI Condition
    rsi_now = df.loc[idx, 'rsi']
    rsi_prev = df.loc[idx-1, 'rsi']
    rsi_delta = df.loc[idx, 'rsi_delta']
    print(f"1. RSI STATUS:")
    print(f"   - Level: {rsi_now:.2f} (Prev: {rsi_prev:.2f})")
    print(f"   - Delta (vs EMA): {rsi_delta:.2f}")
    if rsi_delta < 5 and rsi_now > 70:
        print("   -> DIAGNOSIS: 'Coiled Spring' (RSI broken out but EMA close)")
    elif rsi_delta > 10:
        print("   -> DIAGNOSIS: 'Overextended' (RSI flew too fast)")
        
    # 2. Volume
    vol_ratio = df.loc[idx, 'vol_ratio']
    avg_vol_ratio_3 = context['vol_ratio'].mean()
    print(f"\n2. VOLUME ACTIVITY:")
    print(f"   - Instant Surge: {vol_ratio:.2f}x")
    print(f"   - Recent Avg (3 bars): {avg_vol_ratio_3:.2f}x")
    if vol_ratio > 2.0:
        print("   -> DIAGNOSIS: 'Explosive Ignition' (Huge volume spike)")
    
    # 3. Trend
    close = df.loc[idx, 'close']
    ma200 = df.loc[idx, 'ma200']
    dist_ma200 = (close - ma200)/ma200 * 100
    print(f"\n3. TREND CONTEXT:")
    print(f"   - Distance from MA200: {dist_ma200:+.2f}%")
    if dist_ma200 > 10:
        print("   -> DIAGNOSIS: 'Sky High' (Deep in Uptrend)")
    elif dist_ma200 < 0:
        print("   -> DIAGNOSIS: 'Contrarian' (Below MA200)")
        
    # 4. Volatility (The Squeeze)
    bb_widths = context['bb_width'].values
    print(f"\n4. VOLATILITY (Bollinger Width):")
    print(f"   - Last 5 bars: {[f'{w:.2f}%' for w in bb_widths[-5:]]}")
    if bb_widths[-1] > 4:
        print("   -> DIAGNOSIS: 'Volatile Expansion' (Wide Bands)")
    elif bb_widths[-1] < 1.5:
        print("   -> DIAGNOSIS: 'The Squeeze' (Very tight bands)")
        
    print("\n" + "-"*50)
    print("NARRATIVE RECONSTRUCTION:")
    # Simple rule-based summary
    narrative = []
    if rsi_now > 70: narrative.append("Momentum exploded (RSI>70)")
    if rsi_delta < 5: narrative.append("supported by a steady accumulation (Low Delta)")
    if vol_ratio > 1.5: narrative.append("fueled by high volume")
    if dist_ma200 > 5: narrative.append("riding a strong long-term trend")
    
    print(" ".join(narrative) + ".")

if __name__ == "__main__":
    run_autopsy()
