"""
Hierarchical Clustering Analysis
=================================

Dendogram ile optimal cluster sayısını bulur.
Matplotlib olmadan ASCII-based dendrogram + linkage analizi.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from scipy.cluster.hierarchy import dendrogram, linkage, fcluster
from scipy.cluster.hierarchy import inconsistent, maxinconsts
from pathlib import Path

print("=" * 80)
print("HİYERARŞİK CLUSTERING ANALİZİ")
print("=" * 80)

# Load data
df = pd.read_csv('.tezaver_matrix/harmony_mining/diamond_clusters.csv')

# Prepare data
metadata_cols = ['rally_id', 'symbol', 'timeframe', 'entry_time', 'cluster']
numeric_features = df.select_dtypes(include=[np.number]).columns.tolist()
numeric_features = [f for f in numeric_features if f not in metadata_cols]

X = df[numeric_features].fillna(df[numeric_features].mean())

print(f"\n📊 Veri:")
print(f"   Rallies: {len(X)}")
print(f"   Features: {len(numeric_features)}")

# Standardize
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

print("\n⏳ Hierarchical clustering hesaplanıyor...")

# Compute linkage matrix
# Method: 'ward' minimizes variance within clusters (en yaygın)
linkage_matrix = linkage(X_scaled, method='ward')

print("✅ Linkage matrix hesaplandı!")

# Analyze linkage matrix for optimal clusters
print("\n" + "=" * 80)
print("OPTİMAL CLUSTER SAYISI ANALİZİ")
print("=" * 80)

# Method 1: Look at the largest gaps in dendrogram
# The distance increases at each merge
distances = linkage_matrix[:, 2]

# Find largest jumps (indicates natural cut points)
diff = np.diff(distances)
largest_gaps_idx = np.argsort(diff)[-10:][::-1]

print("\n🔍 En Büyük Mesafe Artışları (Doğal Ayrım Noktaları):")
print(f"{'Sıra':<6} {'Merge Adımı':<15} {'Mesafe Artışı':<20} {'Önerilen K'}")
print("-" * 80)

for rank, idx in enumerate(largest_gaps_idx[:5], 1):
    merge_step = idx + 1
    gap = diff[idx]
    # Cluster count = total - merge_step
    suggested_k = len(X) - merge_step
    
    if suggested_k <= 10:  # Only show reasonable K values
        print(f"{rank:<6} {merge_step:<15} {gap:<20.2f} {suggested_k}")

# Method 2: Silhouette Score for different K
from sklearn.metrics import silhouette_score

print("\n📊 Silhouette Skorları (K=2'den K=10'a):")
print(f"{'K':<5} {'Silhouette Score':<20} {'Yorum'}")
print("-" * 80)

best_k = 2
best_score = -1

for k in range(2, 11):
    if k > len(X):
        break
    
    labels = fcluster(linkage_matrix, k, criterion='maxclust')
    score = silhouette_score(X_scaled, labels)
    
    if score > best_score:
        best_score = score
        best_k = k
    
    marker = "⭐ EN İYİ" if k == best_k and k == range(2, 11)[-1] else ""
    
    print(f"{k:<5} {score:<20.3f} ", end="")
    if score > 0.5:
        print("Mükemmel", marker)
    elif score > 0.3:
        print("İyi", marker)
    elif score > 0.1:
        print("Zayıf", marker)
    elif score > 0:
        print("Çok Zayıf", marker)
    else:
        print("Kötü", marker)

print(f"\n✅ Optimal K = {best_k} (Silhouette: {best_score:.3f})")

# Method 3: Inconsistency method
print("\n" + "=" * 80)
print("TUTARSIZLIK (INCONSISTENCY) ANALİZİ")
print("=" * 80)

inconsist = inconsistent(linkage_matrix, d=2)

print("\n📉 Tutarsızlık Değerleri (Son 10 Birleşme):")
print(f"{'Merge':<8} {'Tutarsızlık':<15} {'Yorum'}")
print("-" * 80)

for i in range(min(10, len(inconsist))):
    idx = -(i+1)
    incons = inconsist[idx, 3]  # 4th column is inconsistency coefficient
    
    print(f"{len(inconsist)+idx:<8} {incons:<15.2f} ", end="")
    if incons > 2.0:
        print("⚠️ Büyük atlama - doğal ayrım")
    elif incons > 1.0:
        print("Orta atlama")
    else:
        print("Küçük atlama")

# Create clusters with best K
print("\n" + "=" * 80)
print(f"HIERARCHICAL CLUSTERING SONUÇLARI (K={best_k})")
print("=" * 80)

final_labels = fcluster(linkage_matrix, best_k, criterion='maxclust')

# Add to dataframe
df['hierarchical_cluster'] = final_labels

# Analyze each cluster
print(f"\n📊 Cluster Dağılımı:")

for cluster_id in range(1, best_k + 1):
    cluster_mask = final_labels == cluster_id
    cluster_data = df[cluster_mask]
    
    print(f"\n🔹 Cluster {cluster_id}: {len(cluster_data)} rally")
    
    # Top symbols
    top_symbols = cluster_data['symbol'].value_counts().head(5)
    print(f"   En Çok: {', '.join([f'{sym}({cnt})' for sym, cnt in top_symbols.items()])}")
    
    # Technical profile
    if len(numeric_features) > 0:
        print(f"   Teknik Profil:")
        print(f"     RSI: {cluster_data['rsi'].mean():.1f}")
        print(f"     Price Change: {cluster_data['price_change_pct'].mean():.2f}%")
        print(f"     Volume Ratio: {cluster_data['volume_ratio'].mean():.2f}x")

# Save results
output_dir = Path(".tezaver_matrix/harmony_mining")

# Save with hierarchical clusters
output_file = output_dir / "diamond_hierarchical_clusters.csv"
df.to_csv(output_file, index=False)

print(f"\n✅ Sonuçlar kaydedildi: {output_file}")

# Create comparison report
comparison = []
comparison.append("# Hierarchical vs K-Means Karşılaştırması\n\n")
comparison.append(f"## Hierarchical Clustering (K={best_k})\n")
comparison.append(f"- **Silhouette Score:** {best_score:.3f}\n")
comparison.append(f"- **Optimal K:** {best_k}\n")
comparison.append(f"- **Cluster Boyutları:** {np.bincount(final_labels)[1:].tolist()}\n\n")

comparison.append("## K-Means (K=5)\n")
comparison.append(f"- **Silhouette Score:** -0.735\n")
comparison.append(f"- **Cluster Boyutları:** [63, 1, 18, 1, 29]\n\n")

comparison.append("## Sonuç\n")
if best_score > -0.735:
    comparison.append(f"✅ Hierarchical clustering K-Means'ten **DAHA İYİ** ({best_score:.3f} vs -0.735)\n")
else:
    comparison.append(f"⚠️ Her iki yöntem de zayıf performans gösteriyor.\n")

with open(output_dir / "hierarchical_vs_kmeans.md", 'w') as f:
    f.writelines(comparison)

print(f"✅ Karşılaştırma raporu: hierarchical_vs_kmeans.md")

print("\n" + "=" * 80)
print("ANALİZ TAMAMLANDI!")
print("=" * 80)
