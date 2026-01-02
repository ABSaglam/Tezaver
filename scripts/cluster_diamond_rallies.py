"""
Diamond Rally Clustering Script
================================

Bu script tüm Diamond rallyleri için:
1. Feature extraction yapar (56 özellik)
2. K-Means clustering uygular
3. Grupları raporlar
"""

import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from tezaver.core.rally_store import RallyStore
from tezaver.smyrna.pattern_extractor import PatternExtractor
from tezaver.core.logging_utils import get_logger
from pathlib import Path

logger = get_logger(__name__)


def main():
    logger.info("=" * 70)
    logger.info("DIAMOND RALLY CLUSTERING ANALYSIS")
    logger.info("=" * 70)
    
    # 1. Load Diamond Rallies
    logger.info("\n1. Loading Diamond rallies (15m timeframe)...")
    store = RallyStore()
    rallies = store.list_rallies(tier='DIAMOND', timeframe='15m', limit=9999)
    
    logger.info(f"Found {len(rallies)} Diamond rallies")
    
    if len(rallies) == 0:
        logger.error("No Diamond rallies found!")
        return
    
    # 2. Extract Features
    logger.info("\n2. Extracting features...")
    extractor = PatternExtractor(lookback_bars=7)
    
    rally_list = [
        {
            'rally_id': r['id'],
            'symbol': r['symbol'],
            'timeframe': r['timeframe'],
            'entry_time': pd.Timestamp(r['event_time'])
        }
        for r in rallies
    ]
    
    features_df = extractor.extract_batch(rally_list)
    
    logger.info(f"Extracted features for {len(features_df)} rallies")
    logger.info(f"Total features: {len(features_df.columns)}")
    
    if len(features_df) < 3:
        logger.error("Not enough rallies for clustering!")
        return
    
    # 3. Prepare Data for Clustering
    logger.info("\n3. Preparing data for clustering...")
    
    # Keep metadata
    metadata_cols = ['rally_id', 'symbol', 'timeframe', 'entry_time']
    metadata = features_df[metadata_cols].copy()
    
    # Select numeric features only
    numeric_features = features_df.select_dtypes(include=[np.number]).columns.tolist()
    
    # Remove metadata from numeric features
    numeric_features = [f for f in numeric_features if f not in metadata_cols]
    
    logger.info(f"Using {len(numeric_features)} numeric features for clustering")
    
    X = features_df[numeric_features].copy()
    
    # Handle missing values
    X = X.fillna(X.mean())
    
    # Standardize features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # 4. K-Means Clustering
    logger.info("\n4. Running K-Means clustering...")
    
    # Try different K values
    n_clusters = min(5, len(features_df) // 2)  # Max 5 clusters or half the data
    
    logger.info(f"Clustering into {n_clusters} groups...")
    
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(X_scaled)
    
    # Add cluster labels to metadata
    metadata['cluster'] = cluster_labels
    
    # 5. Generate Report
    logger.info("\n5. Generating cluster report...")
    logger.info("=" * 70)
    logger.info("CLUSTER DISTRIBUTION")
    logger.info("=" * 70)
    
    for cluster_id in range(n_clusters):
        cluster_mask = cluster_labels == cluster_id
        cluster_count = cluster_mask.sum()
        
        logger.info(f"\nCluster {cluster_id}: {cluster_count} rallies")
        
        # Show sample symbols
        sample_symbols = metadata[cluster_mask]['symbol'].value_counts().head(5)
        logger.info("  Top symbols:")
        for sym, count in sample_symbols.items():
            logger.info(f"    {sym}: {count}")
    
    # 6. Save Results
    output_dir = Path(".tezaver_matrix/harmony_mining")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Combine metadata + numeric features + cluster
    full_results = pd.concat([metadata, features_df[numeric_features]], axis=1)
    
    output_file = output_dir / "diamond_clusters.csv"
    full_results.to_csv(output_file, index=False)
    
    logger.info(f"\n✅ Results saved to: {output_file}")
    
    # Create summary report
    summary_lines = []
    summary_lines.append("# Diamond Rally Clustering Report\n")
    summary_lines.append(f"**Total Rallies:** {len(features_df)}\n")
    summary_lines.append(f"**Features Used:** {len(numeric_features)}\n")
    summary_lines.append(f"**Clusters:** {n_clusters}\n\n")
    
    summary_lines.append("## Cluster Distribution\n\n")
    for cluster_id in range(n_clusters):
        cluster_mask = cluster_labels == cluster_id
        cluster_count = cluster_mask.sum()
        cluster_rallies = metadata[cluster_mask]
        
        summary_lines.append(f"### Cluster {cluster_id} ({cluster_count} rallies)\n\n")
        
        # Top symbols
        top_symbols = cluster_rallies['symbol'].value_counts().head(5)
        summary_lines.append("**Top Symbols:**\n")
        for sym, count in top_symbols.items():
            summary_lines.append(f"- {sym}: {count} rallies\n")
        
        summary_lines.append("\n")
    
    summary_file = output_dir / "clustering_summary.md"
    with open(summary_file, 'w') as f:
        f.writelines(summary_lines)
    
    logger.info(f"✅ Summary saved to: {summary_file}")
    
    logger.info("\n" + "=" * 70)
    logger.info("CLUSTERING COMPLETE!")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
