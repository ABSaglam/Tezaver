"""
ADAUSDT Unique Strategy V1 (Final)
===================================
Cardano - Dual Personality: Dip-Buying Focus

GİZEM: ADA ikili karakter - ACM gibi!
1. Dip-buying (daily_ch <= -2%) - 50 sinyal ✅
2. Momentum (mom_5d >= 10%) - 36 sinyal

Büyük coin ama dip-buying ile daha fazla sinyal!

Final Rule:
- daily_ch <= -2%

Train: 2023-2025 | Test: 2026 held out
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

sys.path.insert(0, os.path.dirname(__file__))
from db_helper import get_rallies, TRAIN_CUTOFF

def main():
    symbol = 'ADAUSDT'
    print(f"🎯 {symbol} (Cardano) UNIQUE STRATEGY V1")
    print(f"📅 Train: 2023-2025 | Test: 2026 (held out)")
    print("=" * 70)
    
    rally_results = get_rallies(symbol, tiers=['DIAMOND', 'GOLD', 'SILVER'], train_only=True)
    
    df_1d = pd.read_parquet(coin_cell_paths.get_history_file(symbol, '1d'))
    df_1d = df_1d.sort_values('timestamp').reset_index(drop=True)
    df_1d['datetime'] = pd.to_datetime(df_1d['timestamp'], unit='ms')
    df_1d = df_1d[df_1d['datetime'] < pd.Timestamp(TRAIN_CUTOFF)].reset_index(drop=True)
    df_1d['daily_ch'] = (df_1d['close'] / df_1d['open'] - 1) * 100
    
    signals = []
    
    print(f"\n{'DATE':<12} | {'TYPE':<8} | {'GAIN':<6} | {'DAILY_CH':<8}")
    print("-" * 50)
    
    for idx in range(25, len(df_1d)-1):
        row = df_1d.loc[idx]
        
        # ADA UNIQUE: Dip-buying (Cardano büyük ama dip alımı seviyor!)
        if row['daily_ch'] <= -2:
            next_date = df_1d.loc[idx+1, 'datetime'].date()
            
            if next_date in rally_results:
                tier, gain = rally_results[next_date]
                is_hit = tier in ['DIAMOND', 'GOLD', 'SILVER']
                
                signals.append({'is_hit': is_hit, 'tier': tier, 'gain': gain})
                print(f"{row['datetime'].date()} | {tier:<8} | %{gain:4.1f} | {row['daily_ch']:>6.1f}%")
    
    df = pd.DataFrame(signals)
    print("\n" + "="*60)
    print(f"🎯 {symbol} UNIQUE V1 FINAL (TRAIN DATA)")
    print("="*60)
    if not df.empty:
        print(f"Total Signals: {len(df)}")
        print(f"Precision: {(df['is_hit'].mean()*100):.1f}%")
        print(f"Hits: {df['is_hit'].sum()} | Fails: {len(df) - df['is_hit'].sum()}")
        
        tier_counts = {}
        for s in signals:
            t = s['tier']
            tier_counts[t] = tier_counts.get(t, 0) + 1
        print(f"Tier Breakdown: {tier_counts}")
        print(f"\n📌 2026 test data (19 days) held out")
        print(f"🎭 Cardano'nun sırrı: Büyük coin ama dip-buying ile rally başlatıyor!")

if __name__ == "__main__":
    main()
