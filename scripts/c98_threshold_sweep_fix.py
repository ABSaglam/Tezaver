"""
C98USDT Threshold Sweep - DÜZELTME
===================================
KRITIK: Mantık hatası düzeltildi!
Artık tüm sinyalleri sayıyoruz (rally olan ve olmayan).
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
    print(f"🔬 {symbol} Threshold Sweep - DÜZELTME")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    
    print("\n📊 Test: mom_3d >= 0%")
    print("-" * 70)
    
    signals = []
    for idx in range(25, len(df_1d)-1):
        row = df_1d.loc[idx]
        
        if row['mom_3d'] >= 0:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            is_rally = next_date in rally_results
            signals.append(is_rally)  # ✅ DÜZELTME: Hem True hem False
    
    if signals:
        hits = sum(signals)
        total = len(signals)
        prec = hits / total * 100 if total > 0 else 0
        
        print(f"Toplam Sinyal: {total}")
        print(f"Rally Olan: {hits}")
        print(f"Rally Olmayan: {total - hits}")
        print(f"Precision: {prec:.1f}%")
        
        if prec == 100:
            print("✅ %100 Precision - DOĞRU!")
        else:
            print(f"❌ %{prec:.1f} Precision - DÜŞÜK!")

if __name__ == "__main__":
    main()
