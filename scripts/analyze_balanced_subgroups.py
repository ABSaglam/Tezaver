#!/usr/bin/env python3
"""
Analyze the BALANCED cluster to find sub-groups.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings('ignore')

def main():
    # Load clustered profiles
    df = pd.read_parquet("library/coin_dna/clustered_profiles.parquet")
    
    # Filter BALANCED cluster (cluster 1)
    balanced = df[df['cluster'] == 1].copy()
    print(f"📊 BALANCED Kümesi Analizi: {len(balanced)} koin")
    print("=" * 80)
    
    # Key features for sub-clustering
    key_features = [
        'avg_atr_pct_mean',      # Volatilite
        'atr_variance_mean',     # Volatilite tutarlılığı
        'needle_freq_mean',      # İğne atma sıklığı
        'max_up_move_mean',      # Max yukarı hareket
        'max_down_move_mean',    # Max aşağı hareket
        'rally_freq_per_1000_mean',  # Ralli sıklığı
        'overbought_freq_mean',  # Aşırı alım sıklığı
        'oversold_freq_mean',    # Aşırı satım sıklığı
        'volume_spike_freq_mean', # Hacim spike sıklığı
        'volume_cv_mean',        # Hacim değişkenliği
    ]
    
    available = [f for f in key_features if f in balanced.columns]
    print(f"Kullanılan özellikler: {len(available)}")
    
    X = balanced[available].fillna(balanced[available].median())
    X = X.replace([np.inf, -np.inf], np.nan).fillna(X.median())
    
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Try different K values
    print("\n📈 Alt-küme sayısı değerlendirmesi:")
    results = []
    for k in range(2, 8):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, labels)
        results.append((k, sil))
        print(f"  K={k}: Silhouette={sil:.3f}")
    
    # Best K
    best_k = max(results, key=lambda x: x[1])[0]
    print(f"\n✅ En iyi alt-küme sayısı: {best_k}")
    
    # Final sub-clustering
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    balanced['sub_cluster'] = kmeans.fit_predict(X_scaled)
    
    # Analyze sub-clusters
    print("\n" + "=" * 80)
    print("🔍 ALT-KÜME ANALİZİ")
    print("=" * 80)
    
    for sc in sorted(balanced['sub_cluster'].unique()):
        sub = balanced[balanced['sub_cluster'] == sc]
        print(f"\n--- Alt-Küme {sc} ({len(sub)} koin) ---")
        
        # Key characteristics
        for feat in available[:6]:
            sub_mean = sub[feat].mean()
            bal_mean = balanced[feat].mean()
            diff = ((sub_mean - bal_mean) / bal_mean) * 100 if bal_mean != 0 else 0
            
            indicator = "🔺" if diff > 15 else "🔻" if diff < -15 else "➖"
            short_name = feat.replace('_mean', '').replace('_per_1000', '')
            print(f"  {indicator} {short_name}: {sub_mean:.2f} ({diff:+.0f}%)")
        
        # Example coins
        examples = sub['symbol'].head(8).tolist()
        print(f"  📋 Örnekler: {', '.join([c.replace('USDT', '') for c in examples])}")
        
        # Suggest character
        atr = sub['avg_atr_pct_mean'].mean()
        needle = sub['needle_freq_mean'].mean() if 'needle_freq_mean' in sub.columns else 0
        rally = sub['rally_freq_per_1000_mean'].mean() if 'rally_freq_per_1000_mean' in sub.columns else 0
        oversold = sub['oversold_freq_mean'].mean() if 'oversold_freq_mean' in sub.columns else 0
        
        if oversold > 0.05:
            char = "🐻 DIP-HUNTER (Sık oversold, dip fırsatları)"
        elif rally > 60:
            char = "📈 MOMENTUM (Sık ralli yapan)"
        elif needle > 0.3:
            char = "🎯 WICK-TRADER (İğne ticareti için uygun)"
        elif atr > 3.2:
            char = "⚡ ACTIVE (Hareketli, orta volatilite)"
        elif atr < 2.5:
            char = "🐌 SLOW (Yavaş hareket eden)"
        else:
            char = "⚖️ STANDARD (Normal davranış)"
        
        print(f"  🏷️ Önerilen karakter: {char}")

if __name__ == "__main__":
    main()
