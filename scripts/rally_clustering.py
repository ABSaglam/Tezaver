#!/usr/bin/env python3
"""
🧬 RALLY CLUSTERING — Doğal Rally Gruplarını Bulma

26 rallinin DNA'sından doğal cluster'ları keşfeder.
Her cluster için optimal entry/exit stratejisi belirler.
"""

import json
import numpy as np
from collections import Counter
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

class RallyClusterer:
    """Discovers natural rally clusters"""
    
    def __init__(self, dna_path):
        with open(dna_path, 'r') as f:
            self.dna_data = json.load(f)
    
    def create_feature_vector(self, dna):
        """Convert DNA to numerical feature vector"""
        features = []
        
        # Momentum features
        if dna['momentum']:
            mom_map = {'SLOW': 0, 'GRADUAL': 1, 'AGGRESSIVE': 2, 'EXPLOSIVE': 3}
            features.append(mom_map.get(dna['momentum']['start_type'], 0))
            features.append(dna['momentum']['first_momentum'])
            features.append(dna['momentum']['momentum_acceleration'])
        else:
            features.extend([0, 0, 0])
        
        # Volume features
        if dna['volume']:
            vol_map = {'IRREGULAR': 0, 'BUILDING': 1, 'STEADY_HIGH': 2, 'SPIKE': 3}
            features.append(vol_map.get(dna['volume']['profile_type'], 0))
            features.append(dna['volume']['volume_mean'])
            features.append(dna['volume']['volume_std'])
        else:
            features.extend([0, 0, 0])
        
        # Peak journey features
        if dna['peak_journey']:
            journey_map = {'DIRECT': 0, 'PULLBACK_ONCE': 1, 'GRIND': 2, 'ZIGZAG': 3}
            features.append(journey_map.get(dna['peak_journey']['journey_type'], 0))
            features.append(dna['peak_journey']['time_to_peak'])
            features.append(dna['peak_journey']['pullback_count'])
        else:
            features.extend([0, 0, 0])
        
        # Exhaustion features
        if dna['exhaustion']:
            ex_map = {'SUDDEN': 0, 'GRADUAL': 1, 'SPIKE_CRASH': 2}
            features.append(ex_map.get(dna['exhaustion']['exhaustion_type'], 0))
            features.append(dna['exhaustion']['peak_to_end_candles'])
        else:
            features.extend([0, 0])
        
        # Rally stats
        features.append(dna['rally_pct'])
        
        return np.array(features)
    
    def cluster_rallies(self, n_clusters=4):
        """Cluster rallies into natural groups"""
        print(f"🧬 Clustering 26 rallies into {n_clusters} groups...")
        print("="*80)
        
        # Create feature matrix
        features = []
        for dna in self.dna_data:
            fv = self.create_feature_vector(dna)
            features.append(fv)
        
        X = np.array(features)
        
        # Normalize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)
        
        # K-Means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)
        
        # Group rallies by cluster
        clusters = {}
        for i, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(self.dna_data[i])
        
        return clusters, labels
    
    def analyze_cluster(self, cluster_id, rallies):
        """Analyze characteristics of a cluster"""
        print(f"\n{'='*80}")
        print(f"📊 CLUSTER {cluster_id} — {len(rallies)} rallies")
        print(f"{'='*80}")
        
        # Print dates
        dates = [r['date'] for r in rallies]
        print(f"\nDates: {', '.join(dates[:5])}" + (f" ... (+{len(dates)-5} more)" if len(dates) > 5 else ""))
        
        # Common characteristics
        momentum_types = [r['momentum']['start_type'] for r in rallies if r['momentum']]
        volume_types = [r['volume']['profile_type'] for r in rallies if r['volume']]
        journey_types = [r['peak_journey']['journey_type'] for r in rallies if r['peak_journey']]
        exhaustion_types = [r['exhaustion']['exhaustion_type'] for r in rallies if r['exhaustion']]
        
        print(f"\n🎯 DOMINANT PATTERNS:")
        print(f"  Momentum: {Counter(momentum_types).most_common(1)[0] if momentum_types else 'N/A'}")
        print(f"  Volume: {Counter(volume_types).most_common(1)[0] if volume_types else 'N/A'}")
        print(f"  Journey: {Counter(journey_types).most_common(1)[0] if journey_types else 'N/A'}")
        print(f"  Exhaustion: {Counter(exhaustion_types).most_common(1)[0] if exhaustion_types else 'N/A'}")
        
        # Statistics
        rally_pcts = [r['rally_pct'] for r in rallies]
        print(f"\n📈 STATISTICS:")
        print(f"  Avg Rally %: {np.mean(rally_pcts):.1f}%")
        print(f"  Min/Max Rally %: {min(rally_pcts):.1f}% / {max(rally_pcts):.1f}%")
        
        # Time to peak
        times_to_peak = [r['peak_journey']['time_to_peak'] for r in rallies if r['peak_journey']]
        if times_to_peak:
            print(f"  Avg Time to Peak: {np.mean(times_to_peak):.1f} candles")
        
        # Recommend strategy
        print(f"\n💡 RECOMMENDED STRATEGY:")
        
        # If mostly SLOW momentum + ZIGZAG journey
        if Counter(momentum_types).most_common(1)[0][0] == 'SLOW' and \
           Counter(journey_types).most_common(1)[0][0] == 'ZIGZAG':
            print(f"  Entry: Wait for pullback (F3→F4 pattern)")
            print(f"  Patience: Yüksek (rally yavaş gelişir)")
            print(f"  Exit: LOWER_HIGH + EMA9_BROKEN")
        
        # If mostly DIRECT journey
        elif Counter(journey_types).most_common(1)[0][0] == 'DIRECT':
            print(f"  Entry: İlk COMMITTED sinyali (pullback bekleme)")
            print(f"  Patience: Düşük (hemen hareket eder)")
            print(f"  Exit: İlk zayıflık işaretinde çık")
        
        # If BUILDING volume
        elif Counter(volume_types).most_common(1)[0][0] == 'BUILDING':
            print(f"  Entry: Volume artışı görünce gir")
            print(f"  Patience: Orta")
            print(f"  Exit: Volume drop + LOWER_HIGH")
        
        else:
            print(f"  Entry: Standart COMMITTED koşulları")
            print(f"  Exit: LOWER_HIGH primary")
        
        return {
            'cluster_id': int(cluster_id),
            'size': int(len(rallies)),
            'dates': dates,
            'dominant_momentum': Counter(momentum_types).most_common(1)[0][0] if momentum_types else None,
            'dominant_volume': Counter(volume_types).most_common(1)[0][0] if volume_types else None,
            'dominant_journey': Counter(journey_types).most_common(1)[0][0] if journey_types else None,
            'dominant_exhaustion': Counter(exhaustion_types).most_common(1)[0][0] if exhaustion_types else None,
            'avg_rally_pct': float(np.mean(rally_pcts)),
            'avg_time_to_peak': float(np.mean(times_to_peak)) if times_to_peak else None
        }
    
    def run_analysis(self, n_clusters=4):
        """Run complete clustering analysis"""
        clusters, labels = self.cluster_rallies(n_clusters)
        
        cluster_summaries = []
        for cluster_id, rallies in sorted(clusters.items()):
            summary = self.analyze_cluster(cluster_id, rallies)
            cluster_summaries.append(summary)
        
        # Save results
        output = {
            'n_clusters': n_clusters,
            'clusters': cluster_summaries,
            'rally_assignments': [
                {'date': self.dna_data[i]['date'], 'cluster': int(labels[i])}
                for i in range(len(self.dna_data))
            ]
        }
        
        output_path = "/Users/alisaglam/TezaverMac/data/algo_rally_clusters.json"
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"\n{'='*80}")
        print(f"✅ Clustering analysis complete!")
        print(f"📁 Saved to: {output_path}")
        
        return output

def main():
    dna_path = "/Users/alisaglam/TezaverMac/data/algo_rally_dna.json"
    
    clusterer = RallyClusterer(dna_path)
    results = clusterer.run_analysis(n_clusters=4)
    
    print(f"\n💡 NEXT STEP: Build pattern matching system to identify which cluster a new day belongs to")

if __name__ == "__main__":
    main()
