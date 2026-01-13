#!/usr/bin/env python3
"""
Coin DNA Clustering - Find natural behavioral groups among coins.
Uses K-Means with Elbow Method and Silhouette analysis.
"""

import sys
import os
from pathlib import Path
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)

def load_profiles():
    """Load the extracted DNA profiles."""
    path = Path("library/coin_dna/profiles.parquet")
    if not path.exists():
        raise FileNotFoundError("DNA profiles not found. Run extract_coin_dna.py first.")
    return pd.read_parquet(path)

def prepare_features(df):
    """Prepare features for clustering."""
    # Get numeric columns only
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Remove columns that are mostly NaN
    valid_cols = []
    for col in numeric_cols:
        if df[col].isna().sum() < len(df) * 0.3:  # Less than 30% NaN
            valid_cols.append(col)
    
    print(f"Using {len(valid_cols)} features for clustering")
    
    # Fill remaining NaN with median
    X = df[valid_cols].copy()
    X = X.fillna(X.median())
    
    # Handle infinite values
    X = X.replace([np.inf, -np.inf], np.nan)
    X = X.fillna(X.median())
    
    return X, valid_cols

def find_optimal_clusters(X_scaled, max_k=10):
    """Find optimal number of clusters using Elbow and Silhouette."""
    inertias = []
    silhouettes = []
    
    print("\n📊 Evaluating cluster counts (2 to 10)...")
    
    for k in range(2, max_k + 1):
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        
        inertias.append(kmeans.inertia_)
        sil = silhouette_score(X_scaled, labels)
        silhouettes.append(sil)
        
        print(f"  K={k}: Inertia={kmeans.inertia_:.0f}, Silhouette={sil:.3f}")
    
    # Best K by Silhouette
    best_k = np.argmax(silhouettes) + 2
    
    return best_k, inertias, silhouettes

def analyze_clusters(df, labels, feature_cols):
    """Analyze what makes each cluster unique."""
    df = df.copy()
    df['cluster'] = labels
    
    print("\n" + "=" * 80)
    print("🔍 CLUSTER ANALYSIS")
    print("=" * 80)
    
    cluster_sizes = df['cluster'].value_counts().sort_index()
    print(f"\nCluster sizes:")
    for c, size in cluster_sizes.items():
        print(f"  Cluster {c}: {size} coins ({size/len(df)*100:.1f}%)")
    
    # Key distinguishing features
    key_features = [
        'avg_atr_pct_mean', 'needle_freq_mean', 'max_up_move_mean', 
        'rally_freq_per_1000_mean', 'volume_spike_freq_mean', 'overbought_freq_mean'
    ]
    
    available_features = [f for f in key_features if f in df.columns]
    
    print("\n📈 Cluster Characteristics:")
    for cluster_id in sorted(df['cluster'].unique()):
        cluster_data = df[df['cluster'] == cluster_id]
        print(f"\n--- Cluster {cluster_id} ({len(cluster_data)} coins) ---")
        
        for feat in available_features:
            cluster_mean = cluster_data[feat].mean()
            global_mean = df[feat].mean()
            diff_pct = ((cluster_mean - global_mean) / global_mean) * 100 if global_mean != 0 else 0
            
            indicator = "🔺" if diff_pct > 20 else "🔻" if diff_pct < -20 else "➖"
            print(f"  {indicator} {feat}: {cluster_mean:.2f} (vs avg: {global_mean:.2f}, {diff_pct:+.0f}%)")
        
        # Show example coins
        example_coins = cluster_data['symbol'].head(5).tolist()
        print(f"  📋 Examples: {', '.join([c.replace('USDT', '') for c in example_coins])}")
    
    return df

def suggest_cluster_names(df):
    """Suggest names based on cluster characteristics."""
    suggestions = {}
    
    for cluster_id in sorted(df['cluster'].unique()):
        cluster_data = df[df['cluster'] == cluster_id]
        
        # Determine character based on features
        atr = cluster_data['avg_atr_pct_mean'].mean() if 'avg_atr_pct_mean' in df.columns else 0
        needle = cluster_data['needle_freq_mean'].mean() if 'needle_freq_mean' in df.columns else 0
        rally = cluster_data['rally_freq_per_1000_mean'].mean() if 'rally_freq_per_1000_mean' in df.columns else 0
        
        # Simple naming logic
        if atr > 4 and rally > 5:
            name = "🚀 ROCKET"
        elif needle > 0.02:
            name = "🎯 SNIPER"
        elif atr < 2.5:
            name = "🐢 TURTLE"
        elif rally > 3:
            name = "📈 TRENDY"
        else:
            name = "⚖️ BALANCED"
        
        suggestions[cluster_id] = name
    
    return suggestions

def main():
    print("=" * 80)
    print("🧬 COIN DNA CLUSTERING")
    print("=" * 80)
    
    # Load data
    df = load_profiles()
    print(f"Loaded {len(df)} coin profiles")
    
    # Prepare features
    X, feature_cols = prepare_features(df)
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Find optimal K
    best_k, inertias, silhouettes = find_optimal_clusters(X_scaled)
    print(f"\n✅ Optimal cluster count by Silhouette: {best_k}")
    
    # Final clustering
    kmeans = KMeans(n_clusters=best_k, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X_scaled)
    
    # Analyze
    df_clustered = analyze_clusters(df, labels, feature_cols)
    
    # Suggest names
    names = suggest_cluster_names(df_clustered)
    print("\n🏷️ Suggested Cluster Names:")
    for cid, name in names.items():
        print(f"  Cluster {cid}: {name}")
    
    # Save results
    output_path = Path("library/coin_dna/clustered_profiles.parquet")
    df_clustered.to_parquet(output_path, index=False)
    print(f"\n📁 Saved to: {output_path}")
    
    # Also save a simple mapping
    mapping = df_clustered[['symbol', 'cluster']].copy()
    mapping['cluster_name'] = mapping['cluster'].map(names)
    mapping_path = Path("library/coin_dna/cluster_mapping.csv")
    mapping.to_csv(mapping_path, index=False)
    print(f"📁 Mapping saved to: {mapping_path}")

if __name__ == "__main__":
    main()
