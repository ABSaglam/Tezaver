"""
C98USDT MULTI-TIMEFRAME Brute Force
====================================
4h ve 1h timeframe'lerden momentum göstergelerini kullanarak
%100 precision arıyoruz.
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
    print(f"🔬 {symbol} - MULTI-TIMEFRAME Brute Force")
    print("="*70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    # 1D data
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    df_1d['date'] = df_1d['datetime'].dt.date
    
    # 4H data
    df_4h = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '4h'))
    df_4h = df_4h.sort_values('timestamp').reset_index(drop=True)
    df_4h['datetime'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h = df_4h[df_4h['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    df_4h['date'] = df_4h['datetime'].dt.date
    
    # 4H momentum indicators (son 4h mumu günlük tarih ile eşleştir)
    df_4h['mom_4h_6'] = (df_4h['close'] / df_4h['close'].shift(6) - 1) * 100  # 24 saat
    df_4h['mom_4h_12'] = (df_4h['close'] / df_4h['close'].shift(12) - 1) * 100  # 48 saat
    df_4h['mom_4h_18'] = (df_4h['close'] / df_4h['close'].shift(18) - 1) * 100  # 72 saat
    
    # Her günün son 4h mumunu al
    df_4h_daily = df_4h.groupby('date').last().reset_index()
    
    # 1D data ile birleştir
    df = df_1d.merge(df_4h_daily[['date', 'mom_4h_6', 'mom_4h_12', 'mom_4h_18']], 
                     on='date', how='left')
    
    # 1D momentum
    df['mom_7d'] = (df['close'] / df['close'].shift(7) - 1) * 100
    df['mom_3d'] = (df['close'] / df['close'].shift(3) - 1) * 100
    
    print("\n🔍 4H Timeframe Momentum Strategies:")
    print("-" * 70)
    
    best_prec = 0
    best_rule = None
    best_count = 0
    
    # 4H momentum tek başına
    for m4h in [5, 8, 10, 12, 15, 20]:
        signals = []
        for idx in range(25, len(df)-1):
            row = df.loc[idx]
            if pd.notna(row['mom_4h_12']) and row['mom_4h_12'] >= m4h:
                next_date = df.loc[idx+1, 'datetime'].date()
                is_rally = next_date in rally_results
                signals.append(is_rally)
        
        if len(signals) >= 5:
            hits = sum(signals)
            total = len(signals)
            prec = hits / total * 100
            marker = " ✅" if prec == 100 else ""
            if prec >= 80:
                print(f"  mom_4h_12>={m4h}%: {total} sinyal, {hits} rally → {prec:.1f}%{marker}")
                if prec > best_prec or (prec == best_prec and total > best_count):
                    best_prec = prec
                    best_count = total
                    best_rule = f"mom_4h_12>={m4h}%"
    
    # 4H + 1D kombinasyon
    print("\n🔍 4H + 1D Hybrid:")
    print("-" * 70)
    for m4h in [8, 10, 12, 15]:
        for m7 in [3, 5, 8]:
            signals = []
            for idx in range(25, len(df)-1):
                row = df.loc[idx]
                if pd.notna(row['mom_4h_12']) and row['mom_4h_12'] >= m4h and row['mom_7d'] >= m7:
                    next_date = df.loc[idx+1, 'datetime'].date()
                    is_rally = next_date in rally_results
                    signals.append(is_rally)
            
            if len(signals) >= 5:
                hits = sum(signals)
                total = len(signals)
                prec = hits / total * 100
                marker = " ✅" if prec == 100 else ""
                if prec >= 80:
                    print(f"  mom_4h>={m4h} & mom_7d>={m7}: {total} sinyal → {prec:.1f}%{marker}")
                    if prec > best_prec or (prec == best_prec and total > best_count):
                        best_prec = prec
                        best_count = total
                        best_rule = f"mom_4h_12>={m4h} & mom_7d>={m7}"
    
    print("\n" + "="*70)
    print(f"EN İYİ: {best_prec:.1f}% - {best_rule} ({best_count} sinyal)")

if __name__ == "__main__":
    main()
