import pandas as pd
import numpy as np

def analyze_bplus_diamond():
    df = pd.read_parquet("analysis/signal_correlation_data.parquet")
    
    # Filter for B+ Tier and DIAMOND quality
    target = df[(df['tier'] == 'B+') & (df['hit_tier'] == 'DIAMOND')]
    
    print("\n" + "="*80)
    print("💎 B+ DNA TIER: DIAMOND RALLY DEEP DIVE")
    print("="*80)
    
    if target.empty:
        print("No DIAMOND rallies found for B+ Tier in the current dataset.")
        return
        
    print(f"Total B+ Diamond Rallies found: {len(target)}")
    
    # Archetype Breakdown
    print("\n[Archetype Distribution]")
    arch_dist = target['hit_arch'].value_counts()
    for arch, count in arch_dist.items():
        pct = (count / len(target)) * 100
        print(f"  {arch:<12}: {int(count):>3} ({pct:>5.1f}%)")
        
    # Technical Signature
    print("\n[Technical Signature (Average Values)]")
    sig = target[['atr_pct', 'mid_pct', 'bb_squeeze', 'rsi_4h']].mean()
    print(sig.to_string())
    
    # Max Drawdown during these hits
    print(f"\nAvg Max Drawdown during these hits: {target['max_dd'].mean():.2f}%")
    
    # Identify the "Perfect Entry" conditions for B+ Diamond
    # Filter for hits with < 5% drawdown
    perfect = target[target['max_dd'] >= -5]
    print(f"\nPerfect Entries (Max DD < 5%): {len(perfect)} / {len(target)} ({len(perfect)/len(target)*100:.1f}%)")

if __name__ == "__main__":
    analyze_bplus_diamond()
