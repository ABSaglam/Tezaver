
import sys
import os
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ALGOUSDT'
    print(f"🌙 MIDNIGHT LOCK ANALYSIS: {symbol}")
    print("="*70)

    # 1. Load 4H Data
    h4_path = f"coin_cells/{symbol}/data/history_4h.parquet"
    if not os.path.exists(h4_path):
        print("❌ 4H Data not found!")
        return
        
    df = pd.read_parquet(h4_path)
    df = df.sort_values('timestamp').reset_index(drop=True)
    df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
    df = df[df['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    # 2. Features
    df['rsi'] = 100 - (100 / (1 + (df['close'].diff().where(df['close'].diff() > 0, 0).rolling(14).mean() / (-df['close'].diff().where(df['close'].diff() < 0, 0).rolling(14).mean()))))
    df['vol_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
    df['ema_21'] = df['close'].ewm(span=21).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    df['trend'] = (df['ema_21'] / df['ema_50'] - 1) * 100
    df['hour'] = df['datetime'].dt.hour
    
    # ATR Squeeze (Checking for tight range before 00:00)
    df['tr'] = np.maximum(df['high'] - df['low'], abs(df['close'].shift(1) - df['close']))
    df['atr'] = df['tr'].rolling(14).mean()
    df['atr_ratio'] = df['atr'] / df['close'] * 100
    
    # 3. Filter for MIDNIGHT (00:00)
    # The candle at 00:00 is the start of the new day.
    # We want to check the setup AT this moment.
    midnight = df[df['hour'] == 0].copy().reset_index(drop=True)
    
    # Target: Is today a rally day?
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'], train_only=True)
    rally_dates = set(rally_results.keys())
    
    midnight['is_rally'] = midnight['datetime'].dt.date.isin(rally_dates)
    
    print(f"Total Midnight Candles: {len(midnight)}")
    print(f"Total Rally Days: {midnight['is_rally'].sum()}")
    
    # 4. Refinement Loop
    # Base: The Genetic Winner (RSI:65-75 & Vol<=2.0 & Trend>=10)
    
    print("\n--- BASE RULE CHECK ---")
    mask = (
        (midnight['rsi'] >= 65) &
        (midnight['rsi'] <= 75) &
        (midnight['vol_ratio'] <= 2.2) &
        (midnight['trend'] >= 10)
    )
    
    hits = midnight[mask & midnight['is_rally']]
    fails = midnight[mask & ~midnight['is_rally']]
    
    h = len(hits)
    f = len(fails)
    t = h + f
    p = h/t*100 if t>0 else 0
    print(f"BASE GENETIC: {h}/{t} ({p:.1f}%)")
    
    if f > 0:
        print("\n--- FAILURE FORENSICS ---")
        print(fails[['datetime', 'rsi', 'vol_ratio', 'atr_ratio']].head())

    # 5. ATTEMPT TO FIX WITH ATR SQUEEZE
    print("\n--- REFINEMENT: ATR SQUEEZE ---")
    # Hypothesis: False positives are "Choppy/Volatile" days. Real rallies start from "Quiet/Squeezed" states.
    
    for atr_max in [1.5, 2.0, 2.5, 3.0]:
        mask_refined = mask & (midnight['atr_ratio'] <= atr_max)
        h_ = len(midnight[mask_refined & midnight['is_rally']])
        f_ = len(midnight[mask_refined & ~midnight['is_rally']])
        t_ = h_ + f_
        p_ = h_/t_*100 if t_>0 else 0
        
        if t_ >= 2:
            print(f"ATR < {atr_max}: {h_}/{t_} ({p_:.1f}%)")
            if p_ == 100:
                print(f"✅ FOUND IT! ATR Cap {atr_max} eliminates failures.")

if __name__ == "__main__":
    main()
