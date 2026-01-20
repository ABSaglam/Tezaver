"""
C98USDT Agresif Threshold Sweep
================================
Daha yüksek eşikler ve daha fazla kombinasyon deniyoruz.
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
    print(f"🔬 {symbol} - AGRESİF Threshold Sweep")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    
    df_1d['mom_3d'] = (df_1d['close'] / df_1d['close'].shift(3) - 1) * 100
    df_1d['mom_5d'] = (df_1d['close'] / df_1d['close'].shift(5) - 1) * 100
    df_1d['mom_7d'] = (df_1d['close'] / df_1d['close'].shift(7) - 1) * 100
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    df_1d['ema9'] = df_1d['close'].ewm(span=9, adjust=False).mean()
    df_1d['ema_dist'] = (df_1d['close'] / df_1d['ema9'] - 1) * 100
    
    best_prec = 0
    best_rule = None
    
    print("\n🔍 Çok Agresif Kombinasyonlar:")
    print("-" * 70)
    
    # Çok yüksek eşikler
    for m7 in [10, 12, 15, 20]:
        for ema in [5, 8, 10]:
            for dch in [0, 2, 5]:
                signals = []
                for idx in range(25, len(df_1d)-1):
                    row = df_1d.loc[idx]
                    if row['mom_7d'] >= m7 and row['ema_dist'] >= ema and row['daily_ch'] >= dch:
                        next_date = df_1d.loc[idx+1, 'datetime'].date()
                        is_rally = next_date in rally_results
                        signals.append(is_rally)
                
                if len(signals) >= 5:  # En az 5 sinyal olsun
                    hits = sum(signals)
                    total = len(signals)
                    prec = hits / total * 100
                    
                    if prec > best_prec:
                        best_prec = prec
                        best_rule = f"mom_7d>={m7}, ema_dist>={ema}, daily_ch>={dch}"
                    
                    marker = " ✅" if prec == 100 else ""
                    if prec >= 80 or prec == 100:  # Sadece yüksek olanları göster
                        print(f"  m7>={m7} & ema>={ema} & dch>={dch}: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")
    
    print("\n" + "="*70)
    print(f"En İyi Sonuç: {best_prec:.1f}%")
    print(f"Kural: {best_rule}")

if __name__ == "__main__":
    main()
