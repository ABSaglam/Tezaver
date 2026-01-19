"""
TEMPLATE: Coin-Specific Strategy Template
==========================================
USE THIS AS BASE FOR ALL NEW COIN STRATEGIES
- Prevents database locks with safe connection management
- Filters 2026 data automatically (test holdout)
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

# Import safe database helper
sys.path.insert(0, os.path.dirname(__file__))
from db_helper import safe_db_connection, get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'COINUSDT'  # Change this
    print(f"🔄 Analyzing {symbol}...")
    print(f"⚠️  Using TRAIN data only (up to 2025-12-31)")
    
    # SAFE: Uses context manager, auto-closes connection
    # FILTERED: Only 2023-2025 data (2026 held out for testing)
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    print(f"✓ {len(rally_results)} rallies loaded (2023-2025)")
    
    # Load price data
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    
    # FILTER: Remove 2026 data from price data too
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    print(f"✓ {len(df_1d)} candles loaded (filtered 2026)")
    
    # Calculate indicators
    print("🔄 Calculating indicators...")
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['vol_ma20'] = df_1d['volume'].rolling(20).mean()
    df_1d['vol_ratio'] = df_1d['volume'] / df_1d['vol_ma20']
    print("✓ Indicators ready")
    
    # YOUR ANALYSIS LOGIC HERE
    print(f"\n{'='*70}")
    print(f"📊 {symbol} ANALYSIS (TRAIN DATA: 2023-2025)")
    print(f"{'='*70}")
    
    # Example: Test signals
    signals = []
    for idx in range(25, len(df_1d)-1):
        row = df_1d.loc[idx]
        
        # YOUR STRATEGY RULES HERE
        if row['mom_5d'] >= 30:  # Example condition
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            
            # Check if rally exists in train data
            if next_date in rally_results:
                tier, gain = rally_results[next_date]
                is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                signals.append(is_hit)
    
    if signals:
        hits = sum(signals)
        prec = hits / len(signals) * 100
        print(f"Signals: {len(signals)}, Hits: {hits}, Precision: {prec:.1f}%")
    
    print("\n✅ Analysis complete!")
    print("📌 Remember: 2026 data (19 days) held out for testing")

if __name__ == "__main__":
    main()
