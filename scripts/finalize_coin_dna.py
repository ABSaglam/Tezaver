#!/usr/bin/env python3
"""
Final Coin DNA Classification with 5 categories.
"""

import pandas as pd
import numpy as np
from pathlib import Path

def main():
    df = pd.read_parquet('library/coin_dna/clustered_profiles.parquet')
    
    print("🧬 FİNAL COİN DNA SINIFLANDIRMASI")
    print("=" * 70)
    
    # Start with original clusters
    # Cluster 0 = ROCKET (122)
    # Cluster 1 = BALANCED (309) -> will split
    # Cluster 2 = STABLE (10)
    
    # Define thresholds
    NEEDLE_THRESHOLD = 0.276  # Mean + 1 Std
    ATR_THRESHOLD = 2.8  # Split BALANCED into ACTIVE vs CALM
    
    def assign_final_cluster(row):
        # Stablecoins first
        if row['cluster'] == 2:
            return '🐢 STABLE'
        
        # High needle frequency -> WICK-TRAP
        if row.get('needle_freq_mean', 0) > NEEDLE_THRESHOLD:
            return '🎯 WICK-TRAP'
        
        # ROCKET cluster
        if row['cluster'] == 0:
            return '🚀 ROCKET'
        
        # Split BALANCED by ATR
        if row.get('avg_atr_pct_mean', 0) > ATR_THRESHOLD:
            return '⚡ ACTIVE'
        else:
            return '🌊 CALM'
    
    df['final_cluster'] = df.apply(assign_final_cluster, axis=1)
    
    # Summary
    cluster_counts = df['final_cluster'].value_counts()
    print("\n📊 Küme Dağılımı:")
    for cluster, count in cluster_counts.items():
        pct = count / len(df) * 100
        print(f"  {cluster}: {count} koin ({pct:.1f}%)")
    
    # Detailed characteristics
    print("\n" + "=" * 70)
    print("📈 KÜME KARAKTERİSTİKLERİ")
    print("=" * 70)
    
    features = ['avg_atr_pct_mean', 'needle_freq_mean', 'max_up_move_mean', 
                'rally_freq_per_1000_mean', 'overbought_freq_mean']
    
    for cluster in ['🚀 ROCKET', '⚡ ACTIVE', '🌊 CALM', '🎯 WICK-TRAP', '🐢 STABLE']:
        subset = df[df['final_cluster'] == cluster]
        if len(subset) == 0:
            continue
            
        print(f"\n{cluster} ({len(subset)} koin)")
        print("-" * 40)
        
        for feat in features:
            if feat in subset.columns:
                val = subset[feat].mean()
                global_mean = df[feat].mean()
                diff = ((val - global_mean) / global_mean) * 100 if global_mean != 0 else 0
                indicator = "🔺" if diff > 15 else "🔻" if diff < -15 else "➖"
                short = feat.replace('_mean', '').replace('_per_1000', '').replace('avg_', '')
                print(f"  {indicator} {short}: {val:.2f} ({diff:+.0f}%)")
        
        examples = subset['symbol'].head(6).tolist()
        print(f"  📋 Örnekler: {', '.join([c.replace('USDT', '') for c in examples])}")
    
    # Save final classification
    output = df[['symbol', 'final_cluster']].copy()
    output.columns = ['symbol', 'cluster']
    
    # Also include key metrics
    for col in ['avg_atr_pct_mean', 'needle_freq_mean', 'rally_freq_per_1000_mean']:
        if col in df.columns:
            output[col] = df[col]
    
    output_path = Path('library/coin_dna/final_classification.csv')
    output.to_csv(output_path, index=False)
    print(f"\n📁 Kaydedildi: {output_path}")
    
    # What's next?
    print("\n" + "=" * 70)
    print("🔮 SONRAKİ ADIMLAR")
    print("=" * 70)
    print("""
1. ✅ Coin DNA sınıflandırması tamamlandı (5 küme)
2. ⏳ Ralli DNA sınıflandırması (Diamond/Gold/Silver içinde alt tipler)
3. ⏳ Her küme için giriş/çıkış stratejisi tasarımı:
   - ROCKET: Agresif 15m RSI-Hook, hızlı trailing stop
   - ACTIVE: Orta hızda momentum, 4h trailing
   - CALM: Sabırlı swing, geniş stop
   - WICK-TRAP: Limit order stratejisi, wick yakalama
   - STABLE: İşlem dışı
4. ⏳ Strateji backtesting (her küme ayrı ayrı)
""")

if __name__ == "__main__":
    main()
