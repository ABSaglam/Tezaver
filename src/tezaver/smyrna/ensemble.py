"""
Ensemble Algorithm
==================
"Koro: Tüm Algoritmaların Ortak Kararı"

This algorithm combines results from multiple mining algorithms:
- Backward Elimination
- Genetic Algorithm

APPROACH:
1. Run both algorithms independently
2. Collect their feature selections
3. Use voting mechanism to select consensus features
4. Validate combined result

ADVANTAGE: More robust than single algorithm - reduces overfitting risk.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Set
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from tezaver.core.logging_utils import get_logger
from tezaver.smyrna.backward_elimination import BackwardEliminationMiner
from tezaver.smyrna.genetic_algorithm import GeneticAlgorithmMiner

logger = get_logger(__name__)


class EnsembleMiner:
    """
    Ensemble feature selection combining multiple algorithms.
    """
    
    def __init__(
        self,
        target_feature_count: int = 15,
        voting_threshold: int = 1,  # Min votes to include feature
        cv_folds: int = 3,
        random_state: int = 42
    ):
        """
        Initialize Ensemble miner.
        
        Args:
            target_feature_count: Target number of features
            voting_threshold: Minimum votes for feature inclusion
            cv_folds: Cross-validation folds
            random_state: Random seed
        """
        self.target_feature_count = target_feature_count
        self.voting_threshold = voting_threshold
        self.cv_folds = cv_folds
        self.random_state = random_state
        
        self.algorithm_results = {}
        self.feature_votes = {}
        self.final_features = None
    
    def mine(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> List[str]:
        """
        Run ensemble mining.
        
        Args:
            X: Feature DataFrame
            y: Labels
            
        Returns:
            Consensus feature list
        """
        logger.info("=" * 70)
        logger.info("ENSEMBLE ALGORITHM - Combining Multiple Strategies")
        logger.info("=" * 70)
        
        all_features = list(X.columns)
        
        # CLEANUP: Remove raw price/volume columns
        blacklist = [
            'open', 'high', 'low', 'close', 'volume', 
            'bb_upper', 'bb_middle', 'bb_lower',
            'ema_9', 'ema_21', 'ema_50', 'ema_200',
            'fib_0.236', 'fib_0.382', 'fib_0.618'
        ]
        
        # Filter features for mining
        # Note: We don't filter X here because miners do it internally now/or we pass full X
        # But for voting logic, we should be aware
        valid_features = [f for f in all_features if f not in blacklist]
        
        # 1. Backward Elimination
        logger.info("\n🔍 Running Backward Elimination...")
        be_miner = BackwardEliminationMiner(
            target_feature_count=self.target_feature_count,
            cv_folds=self.cv_folds,
            random_state=self.random_state
        )
        
        try:
            be_features = be_miner.mine(X, y)
            self.algorithm_results['backward_elimination'] = be_features
            logger.info(f"✅ Backward Elimination: {len(be_features)} features")
        except Exception as e:
            logger.warning(f"⚠️ Backward Elimination failed: {e}")
            be_features = []
        
        # 2. Genetic Algorithm
        logger.info("\n🧬 Running Genetic Algorithm...")
        ga_miner = GeneticAlgorithmMiner(
            population_size=30,  # Reduced for speed
            generations=10,      # Reduced for speed
            target_feature_count=self.target_feature_count,
            cv_folds=self.cv_folds,
            random_state=self.random_state
        )
        
        try:
            ga_features = ga_miner.mine(X, y)
            self.algorithm_results['genetic_algorithm'] = ga_features
            logger.info(f"✅ Genetic Algorithm: {len(ga_features)} features")
        except Exception as e:
            logger.warning(f"⚠️ Genetic Algorithm failed: {e}")
            ga_features = []
        
        # 3. Voting
        logger.info("\n🗳️ Voting Mechanism...")
        
        all_selected_features = set(be_features) | set(ga_features)
        
        feature_votes = {}
        for feature in all_selected_features:
            votes = 0
            if feature in be_features:
                votes += 1
            if feature in ga_features:
                votes += 1
            feature_votes[feature] = votes
        
        self.feature_votes = feature_votes
        
        # Sort by votes
        sorted_features = sorted(
            feature_votes.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Select features with minimum votes
        consensus_features = [
            feat for feat, votes in sorted_features
            if votes >= self.voting_threshold
        ]
        
        # Limit to target count (take highest votes first)
        if len(consensus_features) > self.target_feature_count:
            consensus_features = consensus_features[:self.target_feature_count]
        
        self.final_features = consensus_features
        
        # 4. Final Validation
        logger.info("\n📊 Ensemble Results:")
        logger.info(f"Backward Elimination contributed: {len(be_features)} features")
        logger.info(f"Genetic Algorithm contributed: {len(ga_features)} features")
        logger.info(f"Consensus features (votes >= {self.voting_threshold}): {len(consensus_features)}")
        
        # Show voting breakdown
        logger.info("\nFeature Voting Breakdown:")
        for i, (feat, votes) in enumerate(sorted_features[:20], 1):
            in_be = "✓" if feat in be_features else " "
            in_ga = "✓" if feat in ga_features else " "
            selected = "→" if feat in consensus_features else " "
            logger.info(f"  {selected} {i:2d}. [{in_be}BE] [{in_ga}GA] {feat:30s} ({votes} votes)")
        
        # Final cross-validation
        if len(consensus_features) > 0:
            X_consensus = X[consensus_features]
            model = RandomForestClassifier(
                n_estimators=100,
                random_state=self.random_state,
                max_depth=10
            )
            
            cv_scores = cross_val_score(
                model,
                X_consensus,
                y,
                cv=self.cv_folds,
                scoring='accuracy'
            )
            
            logger.info(f"\n✅ Ensemble CV Score: {cv_scores.mean():.4f} (±{cv_scores.std():.4f})")
        
        logger.info("\n" + "=" * 70)
        logger.info("ENSEMBLE COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Final Features: {len(consensus_features)}")
        
        return consensus_features
    
    def get_voting_report(self) -> pd.DataFrame:
        """Get voting breakdown as DataFrame."""
        if not self.feature_votes:
            return pd.DataFrame()
        
        report_data = []
        for feature, votes in self.feature_votes.items():
            report_data.append({
                'feature': feature,
                'votes': votes,
                'in_BE': feature in self.algorithm_results.get('backward_elimination', []),
                'in_GA': feature in self.algorithm_results.get('genetic_algorithm', []),
                'selected': feature in (self.final_features or [])
            })
        
        df = pd.DataFrame(report_data)
        return df.sort_values('votes', ascending=False)


def run_ensemble_example():
    """
    Example usage of Ensemble algorithm.
    
    NOTE: Requires rally data.
    """
    from tezaver.core.rally_store import RallyStore
    
    logger.info("Ensemble Algorithm Example")
    logger.info("=" * 70)
    
    # Load rallies
    store = RallyStore()
    rallies = store.list_rallies(limit=100)
    
    if len(rallies) < 10:
        logger.error("Not enough rallies!")
        return
    
    rally_ids = [r['id'] for r in rallies[:50]]
    
    # Prepare dataset (simplified)
    # In real use, would use BackwardEliminationMiner.prepare_dataset()
    logger.info("NOTE: This is a placeholder example")
    logger.info("Real usage requires proper dataset preparation")
    
    # Initialize ensemble
    miner = EnsembleMiner(
        target_feature_count=15,
        voting_threshold=1,
        cv_folds=3
    )
    
    logger.info("\nEnsemble initialized - ready for real data")


if __name__ == "__main__":
    run_ensemble_example()
