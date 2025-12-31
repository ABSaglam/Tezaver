"""
Cipher Generator - Simyacı Orchestrator
========================================
"Tüm Parçaları Birleştir, Master Cipher Üret"

This is the main orchestrator that combines all Simyacı components
to generate Master Ciphers from rally data.

WORKFLOW:
1. Load rally data (filtered by tier, archetype, coin class)
2. Extract features for each rally
3. Run mining algorithm (Backward Elim, Genetic, or Ensemble)
4. Backtest selected features
5. Generate Master Cipher JSON
6. Save to Vault

CRITICAL: This is the PRIMARY OUTPUT of the entire Simyacı system.
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path
import json

from tezaver.core.rally_store import RallyStore
from tezaver.core.logging_utils import get_logger
from tezaver.smyrna.data_access import get_rally_context
from tezaver.smyrna.feature_engine import extract_all_features
from tezaver.smyrna.backward_elimination import BackwardEliminationMiner
from tezaver.smyrna.genetic_algorithm import GeneticAlgorithmMiner
from tezaver.smyrna.ensemble import EnsembleMiner
from tezaver.smyrna.backtest_engine import BacktestEngine, BacktestConfig

logger = get_logger(__name__)


class CipherGenerator:
    """
    Main orchestrator for Master Cipher generation.
    """
    
    def __init__(
        self,
        vault_dir: Path = Path(".tezaver_matrix/vault/ciphers"),
        algorithm: str = "ensemble"  # "backward", "genetic", "ensemble"
    ):
        """
        Initialize Cipher Generator.
        
        Args:
            vault_dir: Directory to save generated ciphers
            algorithm: Which mining algorithm to use
        """
        self.vault_dir = Path(vault_dir)
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        
        self.algorithm = algorithm
        self.store = RallyStore()
    
    def load_training_rallies(
        self,
        tier: Optional[str] = None,
        archetype: Optional[str] = None,
        coin_class: Optional[str] = None,
        timeframe: str = "15m",
        min_count: int = 30
    ) -> List[Dict]:
        """
        Load rallies for training.
        
        Filters by tier, archetype, coin class, timeframe per Simyacı strategy.
        
        Args:
            tier: Rally tier (DIAMOND, GOLD, etc.)
            archetype: Rally archetype (PHOENIX, GRIND, etc.)
            coin_class: Coin class (A, B, C, D, N)
            timeframe: Target timeframe (15m, 1h, 4h)
            min_count: Minimum rallies required
            
        Returns:
            List of rally documents
        """
        logger.info("Loading training rallies...")
        logger.info(f"Filters: tier={tier}, archetype={archetype}, coin_class={coin_class}, tf={timeframe}")
        
        # Load ALL rallies - same as UI
        all_rallies = self.store.list_rallies(limit=100000)
        
        # Filter - exactly same logic as UI
        filtered = []
        for rally in all_rallies:
            # Check tier
            if tier and rally.get('tier') != tier:
                continue
            
            # Check archetype (from rev_data)
            rev_data = rally.get('rev_data') or {}
            if archetype and rev_data.get('archetype') != archetype:
                continue
            
            # Check coin class
            if coin_class and rev_data.get('coin_class') != coin_class:
                continue
            
            # Check timeframe (CRITICAL - was missing!)
            if rally.get('timeframe') != timeframe:
                continue
            
            # NOTE: Not filtering by APPROVED status (same as UI)
            # Many rallies don't have rev_data populated yet
            
            filtered.append(rally)
        
        logger.info(f"Filtered {len(filtered)}/{len(all_rallies)} rallies")
        
        if len(filtered) < min_count:
            logger.warning(f"Only {len(filtered)} rallies found (min: {min_count})")
            logger.warning("Results may not be reliable!")
        
        return filtered
    
    def prepare_dataset(
        self,
        rallies: List[Dict]
    ) -> Tuple[pd.DataFrame, pd.Series, List[str]]:
        """
        Prepare feature dataset from rallies.
        
        Args:
            rallies: Rally documents
            
        Returns:
            (X, y, rally_ids)
            X = features DataFrame
            y = success labels
            rally_ids = rally IDs for tracking
        """
        logger.info(f"Preparing dataset from {len(rallies)} rallies...")
        
        all_features = []
        all_labels = []
        rally_ids = []
        
        for rally in rallies:
            rally_id = rally['id']
            
            try:
                # Get context
                context = get_rally_context(rally_id, lookback_bars=60)
                
                # Extract features
                features = extract_all_features(context)
                
                # Use last bar (T-0) as feature vector
                feature_vector = features.iloc[-1]
                
                # Label: Success if gain > tier threshold
                # TODO: Define proper success criteria
                raw_data = rally.get('raw_data') or {}
                gain = raw_data.get('future_max_gain_pct', 0)
                
                # Simple threshold: >5% = success
                # FIX: Raw gain is decimal (0.05 = 5%), not scaled (5.0)
                label = 1 if gain > 0.05 else 0
                
                all_features.append(feature_vector)
                all_labels.append(label)
                rally_ids.append(rally_id)
                
            except Exception as e:
                logger.warning(f"Failed to process {rally_id}: {e}")
                continue
        
        X = pd.DataFrame(all_features)
        y = pd.Series(all_labels)
        
        logger.info(f"Dataset ready: {len(X)} samples, {len(X.columns)} features")
        logger.info(f"Positive labels: {y.sum()}/{len(y)} ({y.mean()*100:.1f}%)")
        
        return X, y, rally_ids
    
    def generate_cipher(
        self,
        tier: Optional[str] = None,
        archetype: Optional[str] = None,
        coin_class: Optional[str] = None,
        timeframe: str = "15m"
    ) -> Dict:
        """
        Generate Master Cipher for given filters.
        
        Args:
            tier: Target tier
            archetype: Target archetype
            coin_class: Target coin class
            timeframe: Target timeframe
            
        Returns:
            Master Cipher dictionary
        """
        logger.info("=" * 70)
        logger.info("MASTER CIPHER GENERATION")
        logger.info("=" * 70)
        logger.info(f"Target: tier={tier}, archetype={archetype}, class={coin_class}, tf={timeframe}")
        
        # 1. Load training data
        rallies = self.load_training_rallies(
            tier=tier,
            archetype=archetype,
            coin_class=coin_class,
            timeframe=timeframe
        )
        
        if len(rallies) < 10:
            raise ValueError(f"Insufficient data: {len(rallies)} rallies")
        
        # 2. Prepare dataset
        X, y, rally_ids = self.prepare_dataset(rallies)
        
        # 3. Run mining algorithm
        logger.info(f"\n🧬 Running {self.algorithm} algorithm...")
        
        if self.algorithm == "backward":
            miner = BackwardEliminationMiner(target_feature_count=15)
        elif self.algorithm == "genetic":
            miner = GeneticAlgorithmMiner(target_feature_count=15, generations=10)
        else:  # ensemble
            miner = EnsembleMiner(target_feature_count=15)
        
        selected_features = miner.mine(X, y)
        
        # 4. Backtest
        logger.info(f"\n📊 Backtesting selected features...")
        # TODO: Generate actual signals from features
        # For now, placeholder
        
        # 5. Create Master Cipher
        cipher_id = f"{tier or 'ANY'}_{archetype or 'ANY'}_{coin_class or 'ANY'}_{timeframe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        master_cipher = {
            "cipher_id": cipher_id,
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            
            "target": {
                "tier": tier or "ANY",
                "archetype": archetype or "ANY",
                "timeframe": timeframe,
                "coin_class": coin_class or "ANY"
            },
            
            "entry_rules": {
                "selected_features": selected_features,
                "feature_count": len(selected_features),
                "algorithm_used": self.algorithm
            },
            
            "training_stats": {
                "rally_count": len(rallies),
                "positive_ratio": float(y.mean()),
                "feature_pool_size": len(X.columns)
            },
            
            "lifecycle": {
                "status": "DRAFT",
                "last_updated": datetime.now().isoformat()
            },
            
            "human_readable_summary": {
                "tr": f"{len(selected_features)} özellik ile {tier or 'tüm tier'} rallyleri için DNA şifresi. {len(rallies)} rally ile eğitildi.",
                "en": f"DNA cipher for {tier or 'all tier'} rallies using {len(selected_features)} features. Trained on {len(rallies)} rallies."
            }
        }
        
        # 6. Save to vault
        cipher_path = self.vault_dir / f"{cipher_id}.json"
        with open(cipher_path, 'w') as f:
            json.dump(master_cipher, f, indent=2)
        
        logger.info(f"\n✅ Master Cipher saved: {cipher_path}")
        logger.info("=" * 70)
        
        return master_cipher


def run_cipher_generation_example():
    """
    Example cipher generation workflow.
    """
    logger.info("Cipher Generation Example")
    logger.info("=" * 70)
    
    generator = CipherGenerator(algorithm="ensemble")
    
    try:
        # Generate cipher for Diamond rallies
        cipher = generator.generate_cipher(
            tier="DIAMOND",
            archetype=None,  # All archetypes
            coin_class="B",   # Standard coins
            timeframe="15m"
        )
        
        logger.info("\n🎯 Generated Cipher:")
        logger.info(f"ID: {cipher['cipher_id']}")
        logger.info(f"Features: {cipher['entry_rules']['feature_count']}")
        logger.info(f"Training rallies: {cipher['training_stats']['rally_count']}")
        
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    run_cipher_generation_example()
