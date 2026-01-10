import pandas as pd
import numpy as np

def refine_hp_rules():
    df = pd.read_parquet("analysis/signal_correlation_data.parquet")
    
    print("\n" + "="*50)
    print("🎯 HP RULE REFINEMENT ANALYSIS")
    print("="*50)
    
    # 1. ATR% Quantiles
    print("\n[ATR% Impact on Win Rate]")
    df['atr_q'] = pd.qcut(df['atr_pct'], 10)
    print(df.groupby('atr_q')['is_hit'].mean().sort_values(ascending=False))
    
    # 2. BB Squeeze Quantiles
    print("\n[BB Squeeze Impact on Win Rate]")
    df['bb_q'] = pd.qcut(df['bb_squeeze'], 10, duplicates='drop')
    print(df.groupby('bb_q')['is_hit'].mean().sort_values(ascending=False))
    
    # 3. RSI 4H Impact
    print("\n[RSI 4H Impact on Win Rate]")
    df['rsi_q'] = pd.cut(df['rsi_4h'], bins=[0, 30, 40, 50, 60, 70, 100])
    print(df.groupby('rsi_q')['is_hit'].mean().sort_values(ascending=False))

    # 4. Toxic Zone Detection (-DIAMOND correlation)
    print("\n[Toxic Zone: Conditions for -DIAMOND losses]")
    toxic = df[df['max_dd'] <= -30]
    if not toxic.empty:
        print(f"Total -DIAMOND cases: {len(toxic)}")
        print("\nAvg features for -DIAMOND:")
        print(toxic[['atr_pct', 'mid_pct', 'bb_squeeze', 'rsi_4h']].mean())
    
    # 5. Defining the "HP Filter V2" Candidate
    # Based on the qcuts, let's find a sweet spot
    # Example: ATR% > 10% (Top quantiles)
    # BB Squeeze < 1.2 (Tighter is better?)
    
    hp_candidate = df[
        (df['atr_pct'] > 12) & 
        (df['bb_squeeze'] < 1.15) &
        (df['rsi_4h'] < 45)
    ]
    
    if not hp_candidate.empty:
        print("\n" + "="*50)
        print("🚀 HP FILTER V2 CANDIDATE PERFORMANCE")
        print("="*50)
        print(f"Total HP Signals: {len(hp_candidate)}")
        print(f"HP Win Rate: {hp_candidate['is_hit'].mean()*100:.1f}%")
        
        tier_stats = hp_candidate.groupby('tier')['is_hit'].agg(['count', 'mean'])
        print("\nHP Win Rate by Tier:")
        print(tier_stats.sort_values('mean', ascending=False))

if __name__ == "__main__":
    refine_hp_rules()
