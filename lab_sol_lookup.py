
import pandas as pd
from pathlib import Path
from datetime import timedelta

def analyze_sol_rally():
    symbol = "SOLUSDT"
    target_date = "2025-03-02"
    path = Path(f"/Users/alisaglam/TezaverMac/coin_cells/{symbol}/data/features_15m.parquet")
    
    if not path.exists():
        print("File not found.")
        return
        
    df = pd.read_parquet(path)
    # Normalize
    if 'rsi_15m' in df.columns: df['rsi'] = df['rsi_15m']
    if 'volume_rel_15m' in df.columns: df['volume_rel'] = df['volume_rel_15m']
    elif 'vol_rel' in df.columns: df['volume_rel'] = df['vol_rel']
    
    # Filter around date
    start_ts = pd.to_datetime(target_date) - timedelta(hours=6)
    end_ts = pd.to_datetime(target_date) + timedelta(hours=24)
    
    # Normalize timestamp
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
    subset = df[(df['timestamp'] >= start_ts) & (df['timestamp'] <= end_ts)].copy()
    
    if subset.empty:
        print("No data found for this date.")
        return

    # Calculate Gain for each bar manually to see where the rally starts
    # Since we don't have the pre-calculated future_gain here for just a slice easily without lookahead context
    # We will look at the price action in the window.
    
    min_price = subset['low'].min()
    max_price = subset['high'].max()
    move_pct = (max_price - min_price) / min_price * 100
    
    print(f"🔍 SOLUSDT ANALYSIS: {target_date}")
    print(f"Window High: {max_price} | Low: {min_price} | Move: {move_pct:.1f}%")
    print("="*60)
    
    # Find the START (lowest point before the big run)
    # Or find the point with highest future gain if we had it.
    # Let's simple look at the bars with > 1.5x Volume or significant green candles.
    
    print(f"{'TIME (TR)':<20} | {'PRICE':<8} | {'RSI':<5} | {'VOL':<4} | {'NOTE'}")
    print("-" * 60)
    
    for i, row in subset.iterrows():
        ts_tr = row['timestamp'] + timedelta(hours=3)
        rsi = row.get('rsi', 50)
        vol = row.get('volume_rel', 1.0)
        close = row['close']
        
        note = ""
        if rsi < 30: note += "Oversold "
        if vol > 3.0: note += "HighVol! "
        if vol < 1.0: note += "Quiet "
        
        # Only print impactful bars or start of day
        if vol > 2.0 or rsi < 30 or rsi > 70 or ts_tr.hour in [0, 9, 12, 18]:
             print(f"{str(ts_tr):<20} | {close:<8.2f} | {rsi:>5.1f} | {vol:>4.1f} | {note}")

if __name__ == "__main__":
    analyze_sol_rally()
