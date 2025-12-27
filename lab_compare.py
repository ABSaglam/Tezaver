
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

def run_comparison():
    symbol = "ADAUSDT"
    targets = [
        "2025-10-10 21:15:00",
        "2025-03-02 15:15:00",
        "2025-03-02 06:15:00",
        "2024-11-22 10:00:00",
        "2024-11-09 15:00:00"
    ]
    
    print(f"🔬 COMPARATIVE LAB: Analyzing {len(targets)} Specific Rallies")
    
    path = Path(f"coin_cells/{symbol}/data/history_15m.parquet")
    if not path.exists(): return
    df = pd.read_parquet(path)
    
    # Normalize Time
    if 'timestamp' in df.columns and 'open_time' not in df.columns:
        df['open_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    elif 'open_time' in df.columns:
        df['open_time'] = pd.to_datetime(df['open_time'])
    df = df.sort_values('open_time').reset_index(drop=True)
    
    # Enrichment
    df['rsi'] = calculate_rsi(df['close'], 14)
    df['ma200'] = df['close'].rolling(200).mean() # Trend
    df['vol_ma50'] = df['volume'].rolling(50).mean()
    df['vol_ratio'] = df['volume'] / df['vol_ma50']
    
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    df['bb_width'] = (std20 * 2) / sma20 * 100
    
    results = []
    
    for t_str in targets:
        target_ts = pd.to_datetime(t_str)
        # Handle TZ
        if df['open_time'].dt.tz is not None and target_ts.tz is None:
            target_ts = target_ts.tz_localize('UTC')
        
        # Find exact or closest
        mask = df['open_time'] == target_ts
        if not mask.any():
            print(f"⚠️ {t_str} not found exactly.")
            continue
            
        idx = df.index[mask][0]
        row = df.loc[idx]
        
        # Check Next 24h Gain
        indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=96)
        future = df.loc[idx:].iloc[0:96]
        max_price = future['close'].max()
        gain = (max_price - row['close']) / row['close'] * 100
        
        results.append({
            'time': t_str,
            'gain_24h': gain,
            'rsi': row['rsi'],
            'vol_ratio': row['vol_ratio'],
            'trend_dist': (row['close'] - row['ma200'])/row['ma200']*100,
            'volatility': row['bb_width']
        })
        
    res_df = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print(f"{'TIME':<20} | {'GAIN':<8} | {'RSI':<6} | {'VOL (x)':<8} | {'TREND %':<8} | {'WIDTH %'}")
    print("-" * 80)
    
    for _, r in res_df.iterrows():
        print(f"{r['time']:<20} | {r['gain_24h']:<6.1f}% | {r['rsi']:<6.1f} | {r['vol_ratio']:<8.1f} | {r['trend_dist']:<8.1f} | {r['volatility']:.2f}")
        
    print("-" * 80)
    
    # Synthesize Differences
    print("\n🧐 PATTERN RECOGNITION:")
    
    # Divide into groups
    # Group 1: Contrarian (RSI < 40)
    contrarian = res_df[res_df['rsi'] < 40]
    
    # Group 2: Momentum (RSI > 60)
    momentum = res_df[res_df['rsi'] > 60]
    
    # Group 3: Neutral
    neutral = res_df[(res_df['rsi'] >= 40) & (res_df['rsi'] <= 60)]
    
    if not contrarian.empty:
        print(f"\n1. DİP AVCILARI ({len(contrarian)} Adet):")
        print(f"   Ortalama RSI: {contrarian['rsi'].mean():.1f}")
        print(f"   Ortalama Trend: {contrarian['trend_dist'].mean():.1f}% (MA200 Altı)")
        print("   Hikaye: 'Korku anında alım.'")
        
    if not momentum.empty:
        print(f"\n2. MOMENTUMCULAR ({len(momentum)} Adet):")
        print(f"   Ortalama RSI: {momentum['rsi'].mean():.1f}")
        print(f"   Ortalama Trend: {momentum['trend_dist'].mean():.1f}% (MA200 Üstü)")
        print("   Hikaye: 'Uçuşa katılım.'")

    if not neutral.empty:
        print(f"\n3. SESSİZLER ({len(neutral)} Adet):")
        print(f"   Ortalama RSI: {neutral['rsi'].mean():.1f}")
        print("   Hikaye: 'Sinsi yükseliş.'")

if __name__ == "__main__":
    run_comparison()
