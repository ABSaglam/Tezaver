"""
C98USDT - DIAMOND+GOLD Only Strategy
=====================================
Belki daha yüksek tier rallyleri daha öngörülebilirdir?
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'C98USDT'
    print(f"🔬 {symbol} - DIAMOND+GOLD Only")
    print("="*70)
    
    # Sadece DIAMOND ve GOLD rallyleri
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD'], train_only=True)
    print(f"DIAMOND+GOLD rallies: {len(rally_results)}")
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_7d'] = (df_1d['close'] / df_1d['close'].shift(7) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    
    print("\n🔍 Momentum Strategies (DG only):")
    print("-" * 70)
    
    for m7 in [5, 8, 10, 12, 15, 20]:
        for ema in [0, 3, 5, 8]:
            signals = []
            for idx in range(25, len(df_1d)-1):
                row = df_1d.loc[idx]
                if row['mom_7d'] >= m7 and row['ema_dist'] >= ema:
                    next_date = df_1d.loc[idx+1, 'datetime'].date()
                    is_rally = next_date in rally_results
                    signals.append(is_rally)
            
            if len(signals) >= 3:  # En az 3 sinyal
                hits = sum(signals)
                total = len(signals)
                prec = hits / total * 100
                marker = " ✅" if prec == 100 else ""
                if prec >= 80:
                    print(f"  mom_7d>={m7} & ema>={ema}: {total} sinyal, {hits} DG rally → {prec:.1f}%{marker}")

if __name__ == "__main__":
    main()
