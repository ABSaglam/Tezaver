"""
Natural Cluster Discovery
=========================
Find organic groupings in coin behavior without forcing categories.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))
from tezaver.core import coin_cell_paths

# Load exploration data
data_file = coin_cell_paths.get_library_root() / "coin_exploration.csv"
df = pd.read_csv(data_file)

print("=" * 80)
print("🔍 DOĞAL KÜMELENME KEŞFİ")
print("=" * 80)

# Select features for clustering
features = [
    'diamond_count',
    'total_dsg',
    'avg_trend_duration_days',
    'fakeout_rate_pct',
    'avg_atr_pct',
    'avg_wick_ratio_pct'
]

X = df[features].fillna(0)

# Normalize
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Find optimal number of clusters
print("\n📊 Optimal küme sayısı aranıyor...")
silhouette_scores = []
inertias = []

for k in range(2, 11):
    kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    sil_score = silhouette_score(X_scaled, labels)
    silhouette_scores.append(sil_score)
    inertias.append(kmeans.inertia_)
    print(f"   K={k}: Silhouette={sil_score:.3f}, Inertia={kmeans.inertia_:.1f}")

# Best K based on silhouette
best_k = silhouette_scores.index(max(silhouette_scores)) + 2
print(f"\n✅ En iyi küme sayısı: {best_k} (Silhouette={max(silhouette_scores):.3f})")

# Final clustering
kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
df['cluster'] = kmeans.fit_predict(X_scaled)

print("\n" + "=" * 80)
print(f"📊 {best_k} DOĞAL KÜME BUL UND U")
print("=" * 80)

# Analyze each cluster
for cluster_id in range(best_k):
    cluster_df = df[df['cluster'] == cluster_id]
    
    print(f"\n{'─' * 80}")
    print(f"🔹 KÜME {cluster_id} ({len(cluster_df)} koin)")
    print(f"{'─' * 80}")
    
    # Cluster characteristics
    print(f"Ortalama Diamond: {cluster_df['diamond_count'].mean():.1f}")
    print(f"Ortalama DSG Toplam: {cluster_df['total_dsg'].mean():.1f}")
    print(f"Ortalama Trend Süresi: {cluster_df['avg_trend_duration_days'].mean():.1f} gün")
    print(f"Ortalama Fakeout: {cluster_df['fakeout_rate_pct'].mean():.1f}%")
    print(f"Ortalama ATR: {cluster_df['avg_atr_pct'].mean():.2f}%")
    print(f"Ortalama Wick: {cluster_df['avg_wick_ratio_pct'].mean():.1f}%")
    
    # Top coins in cluster
    top_coins = cluster_df.nlargest(10, 'total_dsg')['symbol'].tolist()
    print(f"\nÖrnek coinler (en çok DSG): {', '.join(top_coins[:10])}")

# Save
output_file = coin_cell_paths.get_library_root() / "coin_natural_clusters.csv"
df.to_csv(output_file, index=False)

print("\n" + "=" * 80)
print(f"✅ Doğal kümeler keşfedildi: {output_file}")
print("=" * 80)
