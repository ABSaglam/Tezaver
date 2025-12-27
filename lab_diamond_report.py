
import pandas as pd
import numpy as np
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0))
    loss = (-delta.where(delta < 0, 0))
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def run_diamond_report():
    symbol = "ADAUSDT"
    print(f"💎 DIAMOND DOSSIER: {symbol} (Target: >30% Gain)")
    
    path = Path(f"coin_cells/{symbol}/data/history_15m.parquet")
    if not path.exists():
        print("Data not found.")
        return
        
    df = pd.read_parquet(path)
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.sort_values('open_time').reset_index(drop=True)
    
    # Enrich
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['ma200'] = df['close'].rolling(200).mean()
    
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    df['bb_width'] = (std20 * 2) / sma20 * 100
    
    df['vol_ma50'] = df['volume'].rolling(50).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma50']
    
    # Identify Rallies (Lookahead)
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=96) # 24 Hours
    df['future_max'] = df['close'].rolling(window=indexer).max()
    df['gain_pot'] = (df['future_max'] - df['close']) / df['close'] * 100
    
    # Filter Diamonds
    # Logic: Gain > 30% AND it wasn't already high (filter consecutive bars)
    # We take local peaks of gain potential to avoid 100 bars of the same rally
    
    diamonds = []
    
    # Simple deduplication: Skip if close to previous
    last_idx = -1000
    
    candidates = df[df['gain_pot'] > 30.0].index
    
    for idx in candidates:
        if idx - last_idx < 32: # Same rally (reduced from 96)
            continue
            
        last_idx = idx
        row = df.loc[idx]
        
        # Profile
        diamonds.append({
            'time': row['open_time'],
            'gain': row['gain_pot'],
            'rsi': row['rsi'],
            'volatility': row['bb_width'],
            'vol_ratio': row['vol_ratio'],
            'trend_dist': (row['close'] - row['ma200'])/row['ma200']*100
        })
        
    diamond_df = pd.DataFrame(diamonds)
    
    print(f"\nFOUND {len(diamond_df)} DIAMOND RALLIES (Gain > 30% in 24h)")
    if len(diamond_df) == 0:
        print("No diamonds found. Try Gold (>20%).")
        return

    print("\n" + "="*60)
    print("💎 DIAMOND PROFILE (AVERAGES)")
    print("="*60)
    print(f"AVG GAIN:       {diamond_df['gain'].mean():.2f}%")
    print(f"RSI START:      {diamond_df['rsi'].mean():.2f} (Neutral/Low?)")
    print(f"VOLATILITY:     {diamond_df['volatility'].mean():.2f}% (High/Low?)")
    print(f"VOLUME SURGE:   {diamond_df['vol_ratio'].mean():.2f}x")
    print(f"TREND DISTANCE: {diamond_df['trend_dist'].mean():.2f}% (vs MA200)")

    print("\n" + "="*60)
    print(f"📜 THE LIST (All {len(diamond_df)} Examples)")
    print("="*60)
    # Sort by time to show timeline
    sorted_diamonds = diamond_df.sort_values('time')
    for i, (_, d) in enumerate(sorted_diamonds.iterrows()):
        print(f"{i+1}. {d['time']} | Gain: {d['gain']:.1f}% | RSI: {d['rsi']:.1f} | Vol: {d['vol_ratio']:.1f}x | Trend: {d['trend_dist']:.1f}%")
        
    print("\n" + "="*60)
    print("🔮 DIAMOND DNA SYNTHESIS")
    
    # Logic Interpretation
    avg_rsi = diamond_df['rsi'].mean()
    avg_vol = diamond_df['vol_ratio'].mean()
    
    if avg_rsi < 40:
        print("TYPE: 'OVERSOLD MONSTERS' (Diamonds are born in fear)")
    elif avg_rsi > 70:
        print("TYPE: 'MOMENTUM RIDERS' (Diamonds are born in hype)")
    else:
        print("TYPE: 'STEALTH EXPLOSIONS' (Diamonds are born in silence)")
        
    if avg_vol > 3:
        print("FUEL: 'HIGH OCTANE' (Needs massive volume)")
    else:
        print("FUEL: 'ORGANIC GROWTH' (Steady volume)")

if __name__ == "__main__":
    run_diamond_report()
