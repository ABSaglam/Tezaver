
import pandas as pd
import numpy as np
from pathlib import Path

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def find_imposter():
    path = Path("coin_cells/ADAUSDT/data/history_15m.parquet")
    if not path.exists(): return

    print("SEARCHING FOR IMPOSTER...")
    df = pd.read_parquet(path)
    
    # Normalize Time
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
    
    df = df.sort_values('open_time').reset_index(drop=True)

    # Indicators
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['vol_ma50'] = df['volume'].rolling(50).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma50']
    
    # "Explosion" Lookalikes
    # High RSI, Huge Volume
    candidates = df[(df['rsi'] > 80) & (df['vol_ratio'] > 5)].copy()
    
    print(f"Candidates with Explosion Profile: {len(candidates)}")
    
    # Check Outcome (Next 32 bars)
    results = []
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=32)
    df['future_max'] = df['close'].rolling(window=indexer).max()
    
    for idx in candidates.index:
        entry = df.loc[idx]
        future_high = df.loc[idx, 'future_max']
        gain = (future_high - entry['close']) / entry['close'] * 100
        
        # We want a FAILURE (Gain < 2%) despite the explosion
        if gain < 2.0:
            results.append({
                'time': entry['open_time'],
                'rsi': entry['rsi'],
                'vol_ratio': entry['vol_ratio'],
                'gain': gain
            })
            
    res_df = pd.DataFrame(results)
    if not res_df.empty:
        # Get the worst failure (lowest gain)
        worst = res_df.sort_values('gain').iloc[0]
        print("\nFOUND THE PERFECT IMPOSTER:")
        print(f"Time: {worst['time']}")
        print(f"RSI: {worst['rsi']:.2f}")
        print(f"Volume: {worst['vol_ratio']:.2f}x")
        print(f"Result: {worst['gain']:.2f}% (FAILED)")
    else:
        print("No imposters found. Maybe high volume always works?")

if __name__ == "__main__":
    find_imposter()
