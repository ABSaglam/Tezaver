import json
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans
from tqdm import tqdm

class DNATierClusterr:
    def __init__(self, profile_dir="DNA_Profiles"):
        self.profile_dir = Path(profile_dir)
        with open(self.profile_dir / "coin_DNA_profile.json", "r") as f:
            self.dna_manifest = json.load(f)

    def cluster_coin(self, symbol, profiles):
        if len(profiles) < 3:
            # Not enough data for clustering, assign all to Tier 1 or 2 based on ratio
            for p in profiles:
                p['tier'] = 1 if p['expansion_ratio'] >= 0.20 else 2
            return profiles

        # Prepare feature matrix for clustering
        # We use expansion_ratio and a combined 'quality' metric from DNA
        features = []
        for p in profiles:
            # Use 1d DNA metrics as primary clustering features
            dna_1d = p['dna'].get('1d', {})
            feat = [
                p['expansion_ratio'],
                dna_1d.get('norm_atr', 0),
                dna_1d.get('vol_contraction', 1),
                dna_1d.get('ema_dist', 0)
            ]
            features.append(feat)
        
        X = np.array(features)
        
        # Cluster into 3 tiers (or fewer if unique rows are few)
        n_clusters = min(3, len(np.unique(X, axis=0)))
        if n_clusters < 1: n_clusters = 1
        
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X)
        
        # Map labels to Tiers 1, 2, 3 based on mean expansion ratio of the cluster
        cluster_means = []
        for i in range(n_clusters):
            cluster_means.append((i, np.mean([profiles[j]['expansion_ratio'] for j in range(len(labels)) if labels[j] == i])))
        
        # Sort by expansion ratio descending (Tier 1 is highest)
        sorted_clusters = sorted(cluster_means, key=lambda x: x[1], reverse=True)
        tier_map = {cluster_id: tier+1 for tier, (cluster_id, _) in enumerate(sorted_clusters)}
        
        for j, label in enumerate(labels):
            profiles[j]['tier'] = tier_map[label]
            
        return profiles

    def run(self):
        print("Clustering DNA patterns into Tiers (1, 2, 3)...")
        clustered_manifest = {}
        tier_summary = []
        
        for symbol, profiles in tqdm(self.dna_manifest.items()):
            clustered_profiles = self.cluster_coin(symbol, profiles)
            clustered_manifest[symbol] = clustered_profiles
            
            # Summary stats
            tier_dist = {1: 0, 2: 0, 3: 0}
            for p in clustered_profiles:
                tier_dist[p['tier']] += 1
                
            tier_summary.append({
                "symbol": symbol,
                "total_expansion_days": len(profiles),
                "tier_1_count": tier_dist[1],
                "tier_2_count": tier_dist[2],
                "tier_3_count": tier_dist[3],
                "avg_expansion": round(np.mean([p['expansion_ratio'] for p in profiles]), 4)
            })
            
        # Save clustered manifest
        with open(self.profile_dir / "coin_DNA_profile.json", "w") as f:
            json.dump(clustered_manifest, f, indent=4)
            
        # Save Tier Summary
        pd.DataFrame(tier_summary).to_csv("DNA_TIER_SUMMARY_ALL_COINS.csv", index=False)
        print("\nTier clustering complete. Manifest updated and DNA_TIER_SUMMARY_ALL_COINS.csv generated.")

if __name__ == "__main__":
    clusterer = DNATierClusterr()
    clusterer.run()
