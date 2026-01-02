"""
Backward Elimination Algorithm
===============================
"Gereksizi At, Özü Bul"

This algorithm starts with all 43 features and iteratively removes
the least important ones until only the essential DNA remains.

PROCESS:
1. Start with all features
2. Train model
3. Identify least important feature
4. Remove it
5. Retrain
6. Repeat until performance degrades or target count reached

CRITICAL: Surgeon Protocol applies - rigorous testing required.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Tuple, Optional
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from tezaver.core.logging_utils import get_logger
from tezaver.smyrna.feature_engine import extract_all_features
from tezaver.smyrna.data_access import get_rally_context

logger = get_logger(__name__)


class BackwardEliminationMiner:
    """
    Backward Elimination feature selection for rally DNA discovery.
    
    Uses Random Forest feature importances to eliminate weak features.
    """
    
    def __init__(
        self,
        target_feature_count: int = 15,
        min_importance_threshold: float = 0.001,
        cv_folds: int = 5,
        random_state: int = 42
    ):
        """
        Initialize Backward Elimination miner.
        
        Args:
            target_feature_count: Stop when this many features remain
            min_importance_threshold: Minimum feature importance to keep
            cv_folds: Cross-validation folds
            random_state: Random seed for reproducibility
        """
        self.target_feature_count = target_feature_count
        self.min_importance_threshold = min_importance_threshold
        self.cv_folds = cv_folds
        self.random_state = random_state
        
        self.elimination_history = []
        self.final_features = None
        self.feature_importances = None
    
    def prepare_dataset(
        self,
        rally_ids: List[str]
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training dataset from rally IDs.
        
        Args:
            rally_ids: List of rally IDs to train on
            
        Returns:
            (X, y) where X = features DataFrame, y = labels (1 = success)
        """
        logger.info(f"Preparing dataset from {len(rally_ids)} rallies...")
        
        all_features = []
        all_labels = []
        
        for rally_id in rally_ids:
            try:
                # Get rally context
                context = get_rally_context(rally_id, lookback_bars=60)
                
                # Extract features
                features = extract_all_features(context)
                
                # Use last bar (T-0) as the feature vector
                feature_vector = features.iloc[-1]
                
                # Label: 1 if rally was successful (TODO: define success criteria)
                # For now, placeholder logic
                label = 1  # Will be replaced with actual rally success metric
                
                all_features.append(feature_vector)
                all_labels.append(label)
                
            except Exception as e:
                logger.warning(f"Failed to process rally {rally_id}: {e}")
                continue
        
        X = pd.DataFrame(all_features)
        
        # CLEANUP: Remove raw price/volume columns that cause overfitting
        # We only want RELATIVE features (Ratios, % changes, Oscillators)
        blacklist = [
            'open', 'high', 'low', 'close', 'volume', 
            'bb_upper', 'bb_middle', 'bb_lower',
            'ema_9', 'ema_21', 'ema_50', 'ema_200', # MA values are absolute prices
            'fib_0.236', 'fib_0.382', 'fib_0.618'   # Fib levels are absolute prices
        ]
        
        # Drop columns if they exist
        cols_to_drop = [c for c in blacklist if c in X.columns]
        if cols_to_drop:
            logger.info(f"Dropping {len(cols_to_drop)} raw value columns to ensure generalization.")
            X = X.drop(columns=cols_to_drop)

        y = pd.Series(all_labels)
        
        logger.info(f"Dataset prepared: {len(X)} samples, {len(X.columns)} features")
        
        return X, y
    
    def evaluate_features(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        features: List[str]
    ) -> Tuple[float, Dict[str, float]]:
        """
        Evaluate feature subset performance.
        
        Args:
            X: Full feature DataFrame
            y: Labels
            features: Feature subset to evaluate
            
        Returns:
            (cv_score, feature_importances)
        """
        X_subset = X[features]
        
        # Train Random Forest
        model = RandomForestClassifier(
            n_estimators=100,
            random_state=self.random_state,
            max_depth=10,
            min_samples_split=5
        )
        
        # Cross-validation score
        cv_scores = cross_val_score(
            model,
            X_subset,
            y,
            cv=self.cv_folds,
            scoring='accuracy'
        )
        
        mean_score = cv_scores.mean()
        
        # Get feature importances
        model.fit(X_subset, y)
        importances = dict(zip(features, model.feature_importances_))
        
        return mean_score, importances
    
    def mine(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> List[str]:
        """
        Run backward elimination on dataset.
        
        Args:
            X: Feature DataFrame
            y: Labels
            
        Returns:
            List of selected feature names
        """
        logger.info("Starting Backward Elimination...")
        logger.info(f"Initial features: {len(X.columns)}")
        logger.info(f"Target features: {self.target_feature_count}")
        
        current_features = list(X.columns)
        best_score = 0.0
        
        iteration = 0
        
        while len(current_features) > self.target_feature_count:
            iteration += 1
            logger.info(f"\n--- Iteration {iteration} ---")
            logger.info(f"Current features: {len(current_features)}")
            
            # Evaluate current feature set
            score, importances = self.evaluate_features(X, y, current_features)
            
            logger.info(f"CV Score: {score:.4f}")
            
            # Track best score
            if score > best_score:
                best_score = score
            
            # Find least important feature
            least_important = min(importances, key=importances.get)
            least_importance = importances[least_important]
            
            logger.info(f"Removing: {least_important} (importance: {least_importance:.6f})")
            
            # Record elimination
            self.elimination_history.append({
                'iteration': iteration,
                'features_count': len(current_features),
                'removed_feature': least_important,
                'importance': least_importance,
                'cv_score': score
            })
            
            # Check if removing this feature would degrade performance too much
            # Test removal
            test_features = [f for f in current_features if f != least_important]
            test_score, _ = self.evaluate_features(X, y, test_features)
            
            score_drop = score - test_score
            
            if score_drop > 0.05:  # More than 5% drop
                logger.warning(f"Removing {least_important} would drop score by {score_drop:.4f}")
                logger.warning("Stopping elimination to preserve performance")
                break
            
            # Remove least important feature
            current_features.remove(least_important)
        
        # Final evaluation
        final_score, final_importances = self.evaluate_features(X, y, current_features)
        
        self.final_features = current_features
        self.feature_importances = final_importances
        
        logger.info("\n" + "=" * 70)
        logger.info("BACKWARD ELIMINATION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Final features: {len(current_features)}")
        logger.info(f"Final CV score: {final_score:.4f}")
        logger.info(f"Best score during elimination: {best_score:.4f}")
        
        # Show top 10 features
        logger.info("\nTop 10 Features by Importance:")
        sorted_features = sorted(
            final_importances.items(),
            key=lambda x: x[1],
            reverse=True
        )
        for i, (feat, imp) in enumerate(sorted_features[:10], 1):
            logger.info(f"  {i:2d}. {feat:30s} {imp:.6f}")
        
        return current_features
    
    def get_elimination_report(self) -> pd.DataFrame:
        """Get elimination history as DataFrame."""
        return pd.DataFrame(self.elimination_history)


def run_backward_elimination_example():
    """
    Example usage of Backward Elimination.
    
    NOTE: Requires rally IDs with available data.
    """
    from tezaver.core.rally_store import RallyStore
    
    logger.info("Backward Elimination Example")
    logger.info("=" * 70)
    
    # Load rallies
    store = RallyStore()
    rallies = store.list_rallies(limit=100)
    
    if len(rallies) < 10:
        logger.error("Not enough rallies for training!")
        return
    
    rally_ids = [r['id'] for r in rallies[:50]]  # Use first 50
    
    # Initialize miner
    miner = BackwardEliminationMiner(
        target_feature_count=15,
        cv_folds=3,  # Lower for speed
        random_state=42
    )
    
    # Prepare dataset
    X, y = miner.prepare_dataset(rally_ids)
    
    if len(X) < 10:
        logger.error("Dataset too small!")
        return
    
    # Run elimination
    selected_features = miner.mine(X, y)
    
    # Show report
    report = miner.get_elimination_report()
    print("\nElimination Report:")
    print(report.to_string())
    
    print(f"\nFinal Selected Features ({len(selected_features)}):")
    for i, feat in enumerate(selected_features, 1):
        print(f"  {i:2d}. {feat}")


if __name__ == "__main__":
    run_backward_elimination_example()
