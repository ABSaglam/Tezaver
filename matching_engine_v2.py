import json
import pandas as pd
import numpy as np
from pathlib import Path

class DNAMatchingEngineV2:
    def __init__(self, profile_dir="DNA_Profiles"):
        self.profile_dir = Path(profile_dir)
        with open(self.profile_dir / "rolling_DNA_profile.json", "r") as f:
            self.dna_profiles = json.load(f)
        with open(self.profile_dir / "coin_antiDNA_profile.json", "r") as f:
            self.anti_dna_profiles = json.load(f)

    def calculate_similarity(self, current_snapshot, target_dna):
        """Calculates distance using V2 metrics."""
        scores = []
        metrics = ["norm_atr", "range_slope", "ema_dist", "vol_contraction", "volt_ratio", "wick_ratio", "price_std"]
        
        for tf in ["1d", "4h", "1h"]:
            curr_tf = current_snapshot.get(tf)
            targ_tf = target_dna.get(tf)
            if not curr_tf or not targ_tf: continue
            
            diffs = []
            for m in metrics:
                val1 = curr_tf.get(m)
                val2 = targ_tf.get(m)
                if val1 is not None and val2 is not None:
                    diffs.append(abs(val1 - val2))
            
            clean_diffs = [d for d in diffs if not np.isnan(d)]
            if clean_diffs:
                scores.append(np.mean(clean_diffs))
            
        return np.mean(scores) if scores else 1.0

    def get_habitat_score(self, symbol, current_snapshot):
        """Calculates Habitat score (Match with Rolling DNA + Anti-DNA Penalty)."""
        if symbol not in self.dna_profiles:
            return None
        
        # 1. Compare with rolling DNA profiles using WEIGHTED similarity
        weighted_dists = []
        for d in self.dna_profiles[symbol]:
            dist = self.calculate_similarity(current_snapshot, d['dna'])
            weight = d.get('weight', 0.5)
            # Higher weight (0.6) for recent patterns makes them more influential
            # We treat 'distance' as distance / weight? No, we want weight to amplify importance.
            # similarity = 1/(1+dist). Weighted similarity = similarity * weight.
            weighted_dists.append((dist, weight))
            
        # Weighted mean similarity
        total_weight = sum(w for d, w in weighted_dists)
        avg_similarity = sum((1.0 / (1.0 + d)) * w for d, w in weighted_dists) / total_weight
        
        # 2. Anti-DNA Similarity (Penalty Source)
        neg_dists = [self.calculate_similarity(current_snapshot, d['dna']) for d in self.anti_dna_profiles.get(symbol, [])]
        min_neg_dist = min(neg_dists) if neg_dists else 1.0
        
        # raw_penalty is similarity to Anti-DNA (0 to 1)
        raw_penalty = 1.0 / (1.0 + min_neg_dist)
        
        # Exponential Effect (K=4): Penalty stays very low until raw_penalty > 0.7
        # This allows HITS that look 'somewhat' like noise to survive, 
        # but kills ones that look EXACTLY like failed breakouts.
        exp_penalty = (raw_penalty ** 4) * 0.5
        
        final_habitat_score = avg_similarity - exp_penalty
        
        return {
            "symbol": symbol,
            "habitat_score": float(final_habitat_score),
            "raw_similarity": float(avg_similarity),
            "anti_penalty": float(exp_penalty)
        }

if __name__ == "__main__":
    engine = DNAMatchingEngineV2()
    print("V2 Matching Engine (Habitat Layer) ready.")
