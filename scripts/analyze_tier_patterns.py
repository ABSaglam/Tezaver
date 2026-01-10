import pandas as pd
import numpy as np

def analyze_full_pattern_matrix():
    df = pd.read_parquet("analysis/signal_correlation_data.parquet")
    
    print("\n" + "="*100)
    print("🧬 FULL GRANULAR PATTERN MATRIX: DNA TIER vs ARCHETYPE")
    print("="*100)
    
    tiers = ['A', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D']
    
    # Define HP Filters from previous analysis to see patterns in High Prob environment
    # For a general "Clean" breakdown, let's look at signals with ATR% > 10
    df_hp = df[df['atr_pct'] > 10].copy()
    
    all_results = []
    
    for tier in tiers:
        t_data = df_hp[df_hp['tier'] == tier]
        if t_data.empty: continue
        
        # Group by Archetype for this tier
        # Note: hit_arch is only available for hits. For a full matrix, 
        # we need to understand which archetypes are most successful.
        
        # Let's pivot: how many times did each archetype occur as a HIT in this tier
        hits = t_data[t_data['is_hit'] == True]
        arch_counts = hits['hit_arch'].value_counts()
        
        for arch, count in arch_counts.items():
            # Success rate is harder to calculate per archetype because 
            # we don't know the archetype of a FALSE POSITIVE (since it never became a rally).
            # However, we can calculate "Contribution": What % of successful signals in this tier are this pattern.
            contribution = (count / len(hits)) * 100
            
            all_results.append({
                "Tier": tier,
                "Pattern": arch,
                "Hits": int(count),
                "Contribution%": round(contribution, 1),
                "Avg_DD": round(hits[hits['hit_arch'] == arch]['max_dd'].mean(), 2)
            })

    matrix_df = pd.DataFrame(all_results)
    
    # Sort by Tier and then Hits
    tier_order = {t: i for i, t in enumerate(tiers)}
    matrix_df['tier_idx'] = matrix_df['Tier'].map(tier_order)
    matrix_df = matrix_df.sort_values(['tier_idx', 'Hits'], ascending=[True, False]).drop(columns=['tier_idx'])
    
    # Display per Tier
    for tier in tiers:
        t_res = matrix_df[matrix_df['Tier'] == tier]
        if t_res.empty: continue
        print(f"\n[{tier} TIER - Pattern Breakdown]")
        print(t_res[['Pattern', 'Hits', 'Contribution%', 'Avg_DD']].to_string(index=False))
        print("-" * 40)

    # Save to CSV for report integration if needed
    matrix_df.to_csv("analysis/tier_archetype_matrix.csv", index=False)
    print("\nFull matrix exported to analysis/tier_archetype_matrix.csv")

if __name__ == "__main__":
    analyze_full_pattern_matrix()
