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
            f = self._extract_features(Path(row['bundle_dir']), row.get('event_time_iso'))
            if f:
                features.append(f)
                valid_ids.append(row['bundle_id'])
                
        if not features:
            return {"error": "Could not extract features from any bundle."}
            
        if len(features) < n_clusters:
            return {"error": f"Not enough valid samples ({len(features)}) for {n_clusters} clusters. Wait for packaging or reduce K."}

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

    def _extract_features(self, bundle_path: Path, event_time_iso: Optional[str] = None) -> Optional[Dict[str, float]]:
        """Extract DNA from a single bundle (Post-Entry)."""
        try:
            # Load price window
            pw_path = bundle_path / "price_window.parquet"
            if not pw_path.exists():
                return None
                
            df = pd.read_parquet(pw_path)
            if df.empty: return None
            
            # Slice From Event Time (Skip Context)
            if event_time_iso:
                try:
                    # Normalize time column
                    time_col = 'open_time' if 'open_time' in df.columns else 'timestamp'
                    if time_col == 'timestamp':
                        df[time_col] = pd.to_datetime(df[time_col], unit='ms', errors='coerce')
                    else:
                        df[time_col] = pd.to_datetime(df[time_col], errors='coerce')
                        
                    event_ts = pd.to_datetime(event_time_iso)
                    
                    # TZ Align
                    if df[time_col].dt.tz is not None and event_ts.tz is None:
                        event_ts = event_ts.tz_localize('UTC')
                    elif df[time_col].dt.tz is None and event_ts.tz is not None:
                        event_ts = event_ts.tz_localize(None)

                    # Find Index
                    mask = df[time_col] >= event_ts
                    idx = mask.idxmax() if mask.any() else 0
                    
                    # Slice (Future Only)
                    df = df.loc[idx:].copy()
                    if df.empty: return None
                except Exception as e:
                    # print(f"Time slicing failed: {e}")
                    pass
            
            # Simple Feature Extraction Logic
            # Assuming 'close' column exists
            if 'close' not in df.columns: return None
            closes = df['close'].values
            
            # 1. Gain (Max - First) / First (Post-Entry)
            start_price = closes[0]
            max_price = np.max(closes)
            peak_idx = np.argmax(closes)
            
            gain = (max_price - start_price) / start_price * 100
            
            # 2. Duration (Time to Peak)
            duration = int(peak_idx)
            
            # 3. Drawdown (Min - Start) / Start
            # Only consider drawdown BEFORE the peak? Or strictly Min? 
            # Usually Max Drawdown during the holding period.
            min_price = np.min(closes)
            max_dd = (min_price - start_price) / start_price * 100
            
            # 4. Volatility
            if len(closes) > 1:
                returns = np.diff(closes) / closes[:-1]
                vol = np.std(returns) * 100
            else:
                vol = 0.0
            
            return {
                "gain": gain,
                "duration": duration,
                "max_dd": max_dd,
                "volatility": vol
            }
        except Exception as e:
            # print(f"Error extracting features for {bundle_path}: {e}")
            return None
