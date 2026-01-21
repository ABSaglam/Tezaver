#!/usr/bin/env python3
"""
🏆 THE TIME SALVAGE REPORT (v12 vs v14)

Bu script, 'Zaman Paradır' felsefesiyle iki modeli karşılaştırır.
Sadece PASS (1H Squeeze) olan günlerde:
- Kaç saat pozisyonda kaldık?
- Ne kadar kâr aldık?
- Ne kadar zaman 'tasarruf' ettik?
"""

import sys
import os
import pandas as pd
import numpy as np
import json
sys.path.append(os.getcwd())

from scripts.asm_v12_turbo import TurboSniper_v12
from scripts.asm_v14_balanced import BalancedSniper_v14

def run_final_audit():
    # 1. Setup Data
    df_h1 = pd.read_parquet("coin_cells/ALGOUSDT/data/history_1h.parquet")
    df_h1['timestamp'] = pd.to_datetime(df_h1['timestamp'], unit='ms')
    df_h1.set_index('timestamp', inplace=True)
    df_h1['ema9'] = df_h1['close'].ewm(span=9, adjust=False).mean()
    df_h1['ema21'] = df_h1['close'].ewm(span=21, adjust=False).mean()
    df_h1['ema50'] = df_h1['close'].ewm(span=50, adjust=False).mean()
    
    def get_comp(row):
        emas = [row['ema9'], row['ema21'], row['ema50']]
        return (max(emas) / min(emas) - 1) * 100
    df_h1['comp'] = df_h1.apply(get_comp, axis=1)
    
    # Ayaş Days in 2023 (1H Squeeze < 2.5%)
    ayas_days = pd.Series(df_h1[(df_h1['comp'] < 2.5) & (df_h1.index.year == 2023)].index).dt.normalize().unique()
    
    df_15m = pd.read_parquet("coin_cells/ALGOUSDT/data/history_15m.parquet")
    df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
    df_15m['ema9'] = df_15m['close'].ewm(span=9, adjust=False).mean()
    df_15m['ema21'] = df_15m['close'].ewm(span=21, adjust=False).mean()
    df_15m['ema50'] = df_15m['close'].ewm(span=50, adjust=False).mean()
    df_15m['vol_ma'] = df_15m['volume'].rolling(20).mean()
    df_15m['vol_ratio'] = df_15m['volume'] / df_15m['vol_ma']
    
    audit_results = []
    
    for day_date in ayas_days:
        day_start = pd.Timestamp(day_date)
        day_end = day_start + pd.Timedelta(days=1)
        day_df = df_15m[(df_15m['timestamp'] >= day_start) & (df_15m['timestamp'] < day_end)]
        if day_df.empty: continue
        
        mock_data = {'date': str(day_date.date()), '15m_data': day_df.to_dict('records')}
        
        # Run v12
        v12 = TurboSniper_v12(mock_data, df_h1).run()
        # Run v14
        v14 = BalancedSniper_v14(mock_data, df_h1).run()
        
        audit_results.append({
            'date': v12['date'],
            'v12_pnl': v12['pnl'] if v12.get('entry_idx') else 0,
            'v12_held': v12['held'] if v12.get('entry_idx') else 0,
            'v14_pnl': v14['pnl'] if v14.get('entry_idx') else 0,
            'v14_held': v14['held'] if v14.get('entry_idx') else 0,
        })

    df_audit = pd.DataFrame(audit_results)
    
    # 2. Aggregates
    v12_total_pnl = df_audit['v12_pnl'].sum()
    v14_total_pnl = df_audit['v14_pnl'].sum()
    v12_total_hours = (df_audit['v12_held'].sum() * 15) / 60
    v14_total_hours = (df_audit['v14_held'].sum() * 15) / 60
    
    saved_hours = v12_total_hours - v14_total_hours
    trades_v12 = len(df_audit[df_audit['v12_held'] > 0])
    trades_v14 = len(df_audit[df_audit['v14_held'] > 0])
    
    print("🏆 FINAL EFFICIENCY AUDIT (ALGO 2023)")
    print("="*80)
    print(f"METRIC            | ASM v12 (Agresif) | ASM v14 (Balanced / Veto)")
    print("-" * 80)
    print(f"Total PnL         | {v12_total_pnl:+.2f}%           | {v14_total_pnl:+.2f}%")
    print(f"Trade Count       | {trades_v12}                | {trades_v14}")
    print(f"Total Screen Time | {v12_total_hours:.1f} Hours         | {v14_total_hours:.1f} Hours")
    print("-" * 80)
    print(f"🚀 SAVED TIME     | {saved_hours:.1f} Hours ({(saved_hours/v12_total_hours)*100:.1f}% less waiting)")
    print(f"💎 EFFICIENCY     | {v12_total_pnl/v12_total_hours:.3f} PnL/Hr       | {v14_total_pnl/v14_total_hours:.3f} PnL/Hr")
    print("="*80)

if __name__ == "__main__":
    run_final_audit()
