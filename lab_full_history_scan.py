
import pandas as pd
import numpy as np
from pathlib import Path

def backtest_archetypes_full_history():
    symbol = "ADAUSDT"
    # Adjust path to where features usually live
    path = Path(f"/Users/alisaglam/TezaverMac/coin_cells/{symbol}/data/features_15m.parquet")
    
    if not path.exists():
        print(f"Features file not found at {path}")
        # Fallback to history if features missing (but we need RSI/Vol)
        return
        
    print(f"📚 LOADING FULL HISTORY for {symbol}...")
    df = pd.read_parquet(path)
    
    # Ensure cols exist
    req_cols = ['close', 'high', 'rsi', 'volume_rel', 'timestamp']
    # Map if names differ (e.g. 'rsi_15m' vs 'rsi')
    # Based on previous outputs, features file usually has 'rsi', 'volume_rel' (or similar)
    # Let's check columns and rename if needed
    
    # Typical Tezaver feature names: 'rsi', 'vol_rel' (or 'volume_rel')
    # Debug: print columns
    # print(df.columns.tolist()) 
    
    # Normalize names
    if 'rsi_15m' in df.columns: df['rsi'] = df['rsi_15m']
    if 'volume_rel_15m' in df.columns: df['volume_rel'] = df['volume_rel_15m']
    if 'vol_rel' in df.columns: df['volume_rel'] = df['vol_rel']
    
    if 'volume_rel' not in df.columns or 'rsi' not in df.columns:
        print("❌ Critical columns (rsi, volume_rel) missing in features.")
        print(f"Available: {df.columns.tolist()}")
        return

    # VECTORIZED LOOKAHEAD (The Oracle)
    # Calculate Max Gain for next 48 bars (12 Hours) for EVERY bar
    lookahead = 48
    
    # Pre-calculate rolling max of 'high' shifted backwards
    # This is heavy, so we use a faster way: 
    # For each row i, max of high[i+1 : i+1+lookahead]
    
    print("🔮 CALCULATING FUTURE GAINS (Oracle Mode)...")
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=lookahead)
    df['future_high_max'] = df['high'].rolling(window=indexer).max().shift(-1) # Shift to align
    
    # Calc gain pct
    df['future_gain_pct'] = (df['future_high_max'] - df['close']) / df['close']
    
    print("🧪 TESTING STRATEGIES (scanning all bars)...")
    print("="*60)
    
    # STRATEGY 1: SUPERNOVA (Volume Explosion)
    # Vol > 5.0
    mask_nova = df['volume_rel'] >= 5.0
    novas = df[mask_nova].copy()
    
    # STRATEGY 2: GRIND (Stealth / Low RSI)
    # Vol < 1.5 AND RSI < 40 (Lowered RSI to filter noise)
    mask_grind = (df['volume_rel'] < 1.5) & (df['rsi'] < 40)
    grinds = df[mask_grind].copy()
    
    # STRATEGY 3: GUILLOTINE (Crash Reversal)
    # RSI < 25 (Extreme)
    mask_guillotine = df['rsi'] < 25
    guillotines = df[mask_guillotine].copy()

    # REPORTING
    def report_strategy(name, subset):
        count = len(subset)
        if count == 0:
            print(f"{name}: No signals found.")
            return
            
        win5 = len(subset[subset['future_gain_pct'] > 0.05])
        win10 = len(subset[subset['future_gain_pct'] > 0.10])
        win20 = len(subset[subset['future_gain_pct'] > 0.20])
        avg_gain = subset['future_gain_pct'].mean()
        max_gain_observed = subset['future_gain_pct'].max()
        
        print(f"\n🦾 STRATEGY: {name}")
        print(f"   Signals: {count} (Frequency: {count/len(df)*100:.2f}%)")
        print(f"   Avg Gain (12h): {avg_gain*100:.2f}%")
        print(f"   Win Rate (>5%): {win5/count*100:.1f}%")
        print(f"   Diamond Rate (>20%): {win20/count*100:.1f}%  <-- THE TREASURE")
        print(f"   Max Historical Win: {max_gain_observed*100:.1f}%")

    report_strategy("💥 SUPERNOVA (Vol > 5.0)", novas)
    report_strategy("🪜 GRIND (Vol < 1.5, RSI < 40)", grinds)
    report_strategy("🩸 GUILLOTINE (RSI < 25)", guillotines)

if __name__ == "__main__":
    backtest_archetypes_full_history()
