import pandas as pd
import numpy as np

def decompose_standard_archetype():
    df = pd.read_parquet("analysis/signal_correlation_data.parquet")
    
    print("\n" + "="*100)
    print("🧬 STANDARD (UNKNOWN) ARCHETYPE DECOMPOSITION: ALPHA, BETA, GAMMA")
    print("="*100)
    
    # Filter for UNKNOWN (Standard) hits or all signals with UNKNOWN status
    # Note: hit_arch is only set for hits. For full win rate analysis, we need to apply rules to ALL signals.
    
    def classify_standard(row):
        # 1. Standard-Alpha (Energetic Momentum): ATR% > 14 + RSI > 60
        if row['atr_pct'] > 14 and row['rsi_4h'] > 60:
            return "Standard-Alpha (Momentum)"
        
        # 2. Standard-Beta (Critical Squeeze): BB Squeeze > 2.5 + RSI 40-60
        if row['bb_squeeze'] > 2.5 and 40 <= row['rsi_4h'] <= 60:
            return "Standard-Beta (Squeeze)"
            
        # 3. Standard-Gamma (Recovery): RSI < 40 + MidPoint < 30
        if row['rsi_4h'] < 40 and row['mid_pct'] < 30:
            return "Standard-Gamma (Recovery)"
            
        return "Standard-General"

    # Apply classification
    df['sub_pattern'] = df.apply(classify_standard, axis=1)
    
    # Analysis
    results = []
    tiers = ['A', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D']
    
    for sub in ["Standard-Alpha (Momentum)", "Standard-Beta (Squeeze)", "Standard-Gamma (Recovery)", "Standard-General"]:
        sub_df = df[df['sub_pattern'] == sub]
        if sub_df.empty: continue
        
        global_win = sub_df['is_hit'].mean()
        
        print(f"\n[Sub-Pattern: {sub}]")
        print(f"  Global Win Rate: {global_win*100:.1f}% ({len(sub_df)} samples)")
        
        # Tier breakdown for this sub-pattern
        tier_win = sub_df.groupby('tier')['is_hit'].agg(['count', 'mean']).sort_values('mean', ascending=False)
        print("  Win Rate by DNA Tier:")
        print(tier_win.to_string())
        
        for tier, row in tier_win.iterrows():
            results.append({
                "Pattern": sub,
                "Tier": tier,
                "Samples": int(row['count']),
                "WinRate%": round(row['mean'] * 100, 1)
            })

    # Final Summary Table
    res_df = pd.DataFrame(results)
    res_df.to_csv("analysis/standard_decomposition_matrix.csv", index=False)
    print("\nDecomposition matrix exported to analysis/standard_decomposition_matrix.csv")

if __name__ == "__main__":
    decompose_standard_archetype()
