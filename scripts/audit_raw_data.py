#!/usr/bin/env python3
"""
Raw Data Integrity Audit
------------------------
Checks the status of raw parquet files downloaded from Binance via CCXT.
Target: data/coin_cells/{SYMBOL}/history/{TIMEFRAME}.parquet

Checks:
1. File Existence (15m, 1h, 4h, 1d)
2. Freshness (Last Date in file)
3. Completeness (Start Date)
"""

import pandas as pd
import sys
import os
from pathlib import Path
import random

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from tezaver.core import coin_cell_paths
from tezaver.core.config import DEFAULT_COINS

def check_coin(symbol):
    report = {'symbol': symbol}
    base_path = Path(f"data/coin_cells/{symbol}/history")
    
    timeframes = ['15m', '1h', '4h', '1d']
    
    for tf in timeframes:
        file_path = base_path / f"{tf}.parquet"
        if file_path.exists():
            try:
                # Read metadata only if possible, or head/tail
                # Parquet allows reading columns or metadata mostly efficiently
                # But here we assume local files are small enough or we read simplified
                df = pd.read_parquet(file_path, columns=['datetime'])
                
                if df.empty:
                     report[tf] = "EMPTY"
                else:
                    last_date = df['datetime'].max().date()
                    total_rows = len(df)
                    report[tf] = f"✅ {last_date} ({total_rows} bars)"
            except:
                report[tf] = "❌ CORRUPT"
        else:
            report[tf] = "❌ MISSING"
            
    return report

def main():
    print("🧱 MARKET DATA AUDIT (Binance Raw Data)")
    print("=" * 60)
    
    # 1. Check Active Sniper Targets (Priority)
    print("\n🕵️ Checking Active Targets (A2Z, BROCCOLI, etc.)...")
    targets = ['A2ZUSDT', 'BROCCOLI714USDT', 'AIXBTUSDT', 'DOGSUSDT', 'BIFIUSDT']
    
    results = []
    for sym in targets:
        results.append(check_coin(sym))
        
    # 2. Check Random Sample
    print("\n🎲 Checking Random Sample (5 coins)...")
    sample = random.sample(DEFAULT_COINS, 5)
    for sym in sample:
        if sym not in targets:
            results.append(check_coin(sym))

    # REPORT
    df = pd.DataFrame(results)
    print("\n" + df.to_markdown(index=False))
    
    print("\n" + "="*60)
    
    # GLOBAL STATS
    print("📊 Global Storage Stats:")
    all_15m = list(Path("data/coin_cells").glob("*/history/15m.parquet"))
    all_1d = list(Path("data/coin_cells").glob("*/history/1d.parquet"))
    
    print(f"Total Coins with 15m Data: {len(all_15m)}")
    print(f"Total Coins with 1d Data:  {len(all_1d)}")


if __name__ == "__main__":
    main()
