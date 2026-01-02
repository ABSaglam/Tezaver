"""
Deep Cluster Analysis Script
=============================

Clustering kalitesini ve ayırt edici özellikleri analiz eder:
1. Cluster cohesion (Silhouette score)
2. Feature importance for clustering
3. Centroid comparison
4. Intra-cluster variance
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, silhouette_samples
from scipy.stats import f_oneway
from pathlib import Path

# Load data
df = pd.read_csv('.tezaver_matrix/harmony_mining/diamond_clusters.csv')

print("=" * 80)
print("DERİN CLUSTER ANALİZİ")
print("=" * 80)

# Prepare data
metadata_cols = ['rally_id', 'symbol', 'timeframe', 'entry_time']
numeric_features = df.select_dtypes(include=[np.number]).columns.tolist()
numeric_features = [f for f in numeric_features if f not in metadata_cols + ['cluster']]

X = df[numeric_features].fillna(df[numeric_features].mean())
labels = df['cluster'].values

print(f"\n📊 Veri Seti:")
print(f"   Toplam Rally: {len(df)}")
print(f"   Numeric Features: {len(numeric_features)}")
print(f"   Cluster Sayısı: {len(np.unique(labels))}")

# 1. CLUSTER QUALITY ANALYSIS
print("\n" + "=" * 80)
print("1. CLUSTER KALİTE ANALİZİ (Silhouette Skorları)")
print("=" * 80)

# Overall silhouette score
overall_silhouette = silhouette_score(X, labels)
print(f"\n✅ Genel Silhouette Skoru: {overall_silhouette:.3f}")
print(f"   Yorum: ", end="")
if overall_silhouette > 0.5:
    print("MÜKEMMEL - Çok belirgin ayrım")
elif overall_silhouette > 0.3:
    print("İYİ - Makul ayrım var")
elif overall_silhouette > 0.1:
    print("ZAYIF - Sınırlar belirsiz")
else:
    print("KÖTÜ - Neredeyse rastgele")

# Per-cluster silhouette
sample_silhouette = silhouette_samples(X, labels)

print("\n📍 Cluster Bazlı Yakınlık:")
for cluster_id in sorted(np.unique(labels)):
    cluster_mask = labels == cluster_id
    cluster_silhouette = sample_silhouette[cluster_mask].mean()
    cluster_size = cluster_mask.sum()
    
    print(f"   Cluster {cluster_id} ({cluster_size:3d} rally): {cluster_silhouette:+.3f}", end="")
    if cluster_silhouette > 0.5:
        print(" ✅ Çok iyi")
    elif cluster_silhouette > 0.3:
        print(" ✓ İyi")
    elif cluster_silhouette > 0:
        print(" ⚠️ Zayıf")
    else:
        print(" ❌ Kötü (yanlış grupta)")

# 2. FEATURE IMPORTANCE ANALYSIS
print("\n" + "=" * 80)
print("2. AYIRT EDİCİ ÖZELLİKLER (ANOVA F-Test)")
print("=" * 80)

# ANOVA for each feature
feature_importance = []

for feature in numeric_features:
    # Get feature values for each cluster
    cluster_groups = [X[labels == c][feature].values for c in sorted(np.unique(labels))]
    
    # ANOVA F-test
    f_stat, p_value = f_oneway(*cluster_groups)
    
    feature_importance.append({
        'feature': feature,
        'f_statistic': f_stat,
        'p_value': p_value
    })

importance_df = pd.DataFrame(feature_importance).sort_values('f_statistic', ascending=False)

print("\n🔍 En Ayırt Edici 15 Özellik:")
print(f"{'Sıra':<5} {'Özellik':<30} {'F-İstatistik':<15} {'p-value':<12} {'Anlam'}")
print("-" * 80)

for idx, row in importance_df.head(15).iterrows():
    f_stat = row['f_statistic']
    p_val = row['p_value']
    
    # Significance
    if p_val < 0.001:
        sig = "***"
    elif p_val < 0.01:
        sig = "**"
    elif p_val < 0.05:
        sig = "*"
    else:
        sig = "ns"
    
    print(f"{idx+1:<5} {row['feature']:<30} {f_stat:>14.2f} {p_val:>11.4f} {sig}")

# 3. CENTROID COMPARISON
print("\n" + "=" * 80)
print("3. CLUSTER MERKEZLERİ KARŞILAŞTIRMASI")
print("=" * 80)

# Calculate centroids
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

centroids = []
for cluster_id in sorted(np.unique(labels)):
    cluster_mask = labels == cluster_id
    centroid = X_scaled[cluster_mask].mean(axis=0)
    centroids.append(centroid)

centroids = np.array(centroids)

# Top differentiating features for each cluster
print("\n🎯 Her Cluster'ı Tanımlayan Özellikler:")

for cluster_id in sorted(np.unique(labels)):
    print(f"\n   CLUSTER {cluster_id}:")
    
    # Find features where this cluster's centroid is most extreme
    centroid = centroids[cluster_id]
    
    # Sort by absolute z-score
    feature_scores = list(zip(numeric_features, centroid))
    feature_scores.sort(key=lambda x: abs(x[1]), reverse=True)
    
    # Top 5 most extreme features
    for feat, score in feature_scores[:5]:
        # Get actual value (un-normalized)
        cluster_mask = labels == cluster_id
        actual_val = X[cluster_mask][feat].mean()
        
        direction = "Yüksek" if score > 0 else "Düşük"
        print(f"      - {feat}: {direction} (z={score:+.2f}, ort={actual_val:.3f})")

# 4. INTRA-CLUSTER VARIANCE
print("\n" + "=" * 80)
print("4. GRUP İÇİ TUTARLILIK (Varyans Analizi)")
print("=" * 80)

print("\n📉 Her Cluster'ın İç Homojenliği:")

for cluster_id in sorted(np.unique(labels)):
    cluster_mask = labels == cluster_id
    cluster_data = X_scaled[cluster_mask]
    
    # Within-cluster variance
    variance = cluster_data.var(axis=0).mean()
    std = cluster_data.std(axis=0).mean()
    
    print(f"   Cluster {cluster_id}: Avg Variance={variance:.3f}, Avg Std={std:.3f}", end="")
    if std < 0.5:
        print(" ✅ Çok homojen")
    elif std < 0.8:
        print(" ✓ Homojen")
    elif std < 1.2:
        print(" ⚠️ Heterojen")
    else:
        print(" ❌ Çok heterojen")

# 5. SAVE DETAILED REPORT
output_dir = Path(".tezaver_matrix/harmony_mining")

# Save importance scores
importance_df.to_csv(output_dir / "feature_importance.csv", index=False)

# Create markdown report
report_lines = []
report_lines.append("# Detaylı Cluster Analizi\n\n")

report_lines.append(f"## Genel Kalite\n")
report_lines.append(f"- **Silhouette Skoru:** {overall_silhouette:.3f}\n")
report_lines.append(f"- **Toplam Rally:** {len(df)}\n")
report_lines.append(f"- **Cluster Sayısı:** {len(np.unique(labels))}\n\n")

report_lines.append(f"## Cluster Silhouette Skorları\n\n")
for cluster_id in sorted(np.unique(labels)):
    cluster_mask = labels == cluster_id
    cluster_silhouette = sample_silhouette[cluster_mask].mean()
    cluster_size = cluster_mask.sum()
    report_lines.append(f"- **Cluster {cluster_id}** ({cluster_size} rally): {cluster_silhouette:.3f}\n")

report_lines.append(f"\n## Top 10 Ayırt Edici Özellikler\n\n")
report_lines.append("| Sıra | Özellik | F-Statistic | p-value |\n")
report_lines.append("|------|---------|-------------|--------|\n")

for idx, row in importance_df.head(10).iterrows():
    report_lines.append(f"| {idx+1} | {row['feature']} | {row['f_statistic']:.2f} | {row['p_value']:.4f} |\n")

with open(output_dir / "deep_analysis_report.md", 'w') as f:
    f.writelines(report_lines)

print("\n" + "=" * 80)
print("✅ Detaylı analiz tamamlandı!")
print(f"📁 Dosyalar:")
print(f"   - feature_importance.csv")
print(f"   - deep_analysis_report.md")
print("=" * 80)
