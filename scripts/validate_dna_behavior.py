"""
Behavioral DNA Validator
========================
Tests if coins in the same Tier actually BEHAVE similarly.
Metric: Reaction to a 5% Pump (Follow-through vs Reversal).
"""

import pandas as pd
import numpy as np
import json
from tezaver.core import coin_cell_paths

def validate_behavior():
    print("=== BEHAVIORAL DNA VALIDATION ===")
    
    with open('library/coin_dna_definitive.json', 'r') as f:
        profiles = json.load(f)
        
    tier_results = {}
    
    # Analyze each tier
    for p in profiles:
        tier = p['tier']
        symbol = p['symbol']
        
        if tier not in tier_results:
            tier_results[tier] = []
            
        try:
            path = coin_cell_paths.get_history_file(symbol, "1d")
            if not path.exists(): continue
            
            df = pd.read_parquet(path)
            if len(df) < 50: continue
            
            # Condition: Local Pump (>5% Green Day)
            df['day_return'] = (df['close'] - df['open']) / df['open'] * 100
            pump_days = df[df['day_return'] >= 5].index
            
            follow_throughs = []
            for idx in pump_days:
                pos = df.index.get_loc(idx)
                if pos + 3 < len(df):
                    # Measure return over next 3 days
                    future_ret = (df.iloc[pos+3]['close'] - df.iloc[pos]['close']) / df.iloc[pos]['close'] * 100
                    follow_throughs.append(future_ret)
            
            if follow_throughs:
                tier_results[tier].extend(follow_throughs)
                
        except:
            continue

    print("\n" + "="*60)
    print(f"{'TIER':<10} | {'SAYI':<6} | {'ORT. TAKİP':<12} | {'BAŞARI %':<10} | {'RİSK (STD)':<10}")
    print("-" * 60)
    
    # Sort tiers appropriately
    tier_order = ['A', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D']
    
    for tier in tier_order:
        if tier not in tier_results or not tier_results[tier]: continue
        
        rets = np.array(tier_results[tier])
        avg_ret = np.mean(rets)
        win_rate = (rets > 0).mean() * 100
        std_dev = np.std(rets)
        
        print(f"{tier:<10} | {len(rets):<6} | {avg_ret:>10.2f}% | {win_rate:>8.1f}% | {std_dev:>8.2f}")

    print("\nAnaliz Notu:")
    print("Ort. Takip: 5% yükseliş sonrası sonraki 3 gündeki ortalama kar/zarar.")
    print("Başarı %: Yükselişin devam etme olasılığı.")
    print("Risk (STD): Davranışın ne kadar 'tutarlı' olduğu (Düşük = Daha benzer davranış).")

if __name__ == "__main__":
    validate_behavior()
