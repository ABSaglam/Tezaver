import json
import pandas as pd
import numpy as np
from pathlib import Path

class DNAMatchingEngine:
    def __init__(self, profile_dir="DNA_Profiles"):
        self.profile_dir = Path(profile_dir)
        with open(self.profile_dir / "coin_DNA_profile.json", "r") as f:
            self.dna_profiles = json.load(f)
        with open(self.profile_dir / "coin_antiDNA_profile.json", "r") as f:
            self.anti_dna_profiles = json.load(f)

    def calculate_similarity(self, current_snapshot, target_dna):
        """Calculates distance between current state and a DNA snapshot using enhanced metrics."""
        scores = []
        metrics = ["norm_atr", "range_slope", "ema_dist", "vol_contraction", "volt_ratio", "price_std"]
        
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

    def get_match_score(self, symbol, current_snapshot, threshold=0.35):
        if symbol not in self.dna_profiles:
            return None
        
        # 1. Compare with all positive DNA profiles, keeping track of Tiers
        tier_matches = {1: [], 2: [], 3: []}
        for d in self.dna_profiles[symbol]:
            dist = self.calculate_similarity(current_snapshot, d['dna'])
            tier = d.get('tier', 3)
            tier_matches[tier].append(dist)
            
        # Best match per tier
        best_tier_dist = {t: (min(dists) if dists else 1.0) for t, dists in tier_matches.items()}
        
        # Overall best match
        min_pos_dist = min(best_tier_dist.values())
        matched_tier = min(best_tier_dist, key=best_tier_dist.get) if min_pos_dist < 1.0 else 3
        
        # 2. Compare with all anti-DNA profiles
        neg_scores = [self.calculate_similarity(current_snapshot, d['dna']) for d in self.anti_dna_profiles.get(symbol, [])]
        min_neg_dist = min(neg_scores) if neg_scores else 1.0
        
        # 3. Final DNA_MATCH_SCORE logic:
        # High score means Close to Positive DNA AND Far from Anti-DNA
        similarity = 1.0 / (1.0 + min_pos_dist)
        penalty = 1.0 / (1.0 + min_neg_dist)
        
        # Tier weighting: Tier 1 matches get a boost, Tier 3 matches are more cautious
        tier_weight = {1: 1.0, 2: 0.8, 3: 0.6}[matched_tier]
        
        # BALANCED ANTI-DNA PENALTY
        final_score = (similarity * tier_weight) - (penalty * 0.55)
        
        return {
            "symbol": symbol,
            "raw_match": float(final_score),
            "matched_tier": matched_tier,
            "is_candidate": final_score > 0.43 # Balanced threshold
        }

if __name__ == "__main__":
    engine = DNAMatchingEngine()
    print("Tier-aware DNA Matching Engine initialized and ready.")
