"""
Foundry Clustering Service (The Alchemist: Mixing Phase)
========================================================

Responsible for taking a set of Approved Bundles and grouping them 
into "Archetypes" using Machine Learning (K-Means).
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

try:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from tezaver.foundry.bundle_index import load_bundle_files

class ClusteringService:
    def __init__(self):
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        
    def cluster_bundles(self, bundle_df: pd.DataFrame, n_clusters: int = 3) -> Dict[str, Any]:
        """
        Clusters a set of bundles into Archetypes.
        
        Args:
            bundle_df: DataFrame of bundles (must have 'bundle_dir').
            n_clusters: Target number of archetypes.
            
        Returns:
            Dict containing cluster_map, centroids, and score.
        """
        if not SKLEARN_AVAILABLE:
            return {"error": "Scikit-learn not available"}
            
        if len(bundle_df) < n_clusters + 1:
            return {"error": "Not enough data points for clustering"}

        # 1. Extract Features (The DNA)
        features = []
        valid_ids = []
        
        for idx, row in bundle_df.iterrows():
            f = self._extract_features(Path(row['bundle_dir']))
            if f:
                features.append(f)
                valid_ids.append(row['bundle_id'])
                
        if not features:
            return {"error": "Could not extract features"}
            
        df_features = pd.DataFrame(features)
        
        # 2. Normalize (The Mixer)
        X = df_features[['gain', 'duration', 'max_dd', 'volatility']].fillna(0)
        X_scaled = self.scaler.fit_transform(X)
        
        # 3. Cluster (The Separation)
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        
        # 4. Analyze Results (The Gold)
        results = {
            "cluster_map": dict(zip(valid_ids, [int(l) for l in labels])),
            "centroids": [],
            "features": df_features.to_dict(orient='records')
        }
        
        # Calculate centroids logic
        df_features['cluster'] = labels
        for i in range(n_clusters):
            cluster_data = df_features[df_features['cluster'] == i]
            if len(cluster_data) > 0:
                centroid = {
                    "cluster_id": i,
                    "count": int(len(cluster_data)),
                    "avg_gain": float(cluster_data['gain'].mean()),
                    "avg_duration": float(cluster_data['duration'].mean()),
                    "avg_vol": float(cluster_data['volatility'].mean()),
                    "member_ids": [valid_ids[j] for j in range(len(valid_ids)) if labels[j] == i]
                }
                results["centroids"].append(centroid)
                
        return results

    def _extract_features(self, bundle_path: Path) -> Optional[Dict[str, float]]:
        """Extract DNA from a single bundle."""
        try:
            # Load price window
            pw_path = bundle_path / "price_window.parquet"
            if not pw_path.exists():
                return None
                
            df = pd.read_parquet(pw_path)
            if df.empty: return None
            
            # Simple Feature Extraction Logic
            # Assuming 'close' column exists
            closes = df['close'].values
            
            # 1. Gain (Max - First) / First
            start_price = closes[0]
            max_price = np.max(closes)
            gain = (max_price - start_price) / start_price * 100
            
            # 2. Duration (Length)
            duration = len(closes)
            
            # 3. Drawdown (Min - Start) / Start (during the move)
            min_price = np.min(closes)
            max_dd = (min_price - start_price) / start_price * 100
            
            # 4. Volatility (Std Dev of returns)
            returns = np.diff(closes) / closes[:-1]
            vol = np.std(returns) * 100
            
            return {
                "gain": gain,
                "duration": duration,
                "max_dd": max_dd,
                "volatility": vol
            }
        except Exception as e:
            # print(f"Error extracting features for {bundle_path}: {e}")
            return None
