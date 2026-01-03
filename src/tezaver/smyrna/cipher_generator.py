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
from tezaver.core.coin_cell_paths import get_history_file
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
    
    def generate_negative_samples(self, count: int, timeframe: str) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Generate synthetic negative samples (noise).
        
        This prevents the 'Survival Bias' where the model only learns successful patterns.
        We sample random points from history that are presumably NOT rallies.
        
        Args:
            count: Number of negative samples needed
            timeframe: Target timeframe
            
        Returns:
            (X_neg, y_neg)
        """
        logger.info(f"Generating {count} negative samples (noise)...")
        
        # Use a high-liquidity coin for noise reference (e.g. BTCUSDT)
        # Ideally we should sample from multiple coins
        # EXPANDED: Include high-beta/volatile coins to prevent domain shift
        ref_symbols = [
            "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", 
            "XRPUSDT", "ADAUSDT", "AVAXUSDT", "DOGEUSDT", 
            "DOTUSDT", "LINKUSDT", "MATICUSDT", "TRXUSDT"
        ]
        
        neg_features_list = []
        
        # Ensure we get enough samples per coin (at least 1, but aim for even distribution)
        samples_per_coin = max(int(np.ceil(count / len(ref_symbols))), 5)
        
        for symbol in ref_symbols:
            try:
                history_path = get_history_file(symbol, timeframe)
                if not history_path.exists():
                    continue
                    
                df = pd.read_parquet(history_path)
                
                # Check df size
                if len(df) < 500:
                    continue
                
                # CRITICAL OPTIMIZATION:
                # Do NOT extract features for entire 2 years (70k+ rows) just to pick 5 samples.
                # Instead, pick indices first, then extract features on a small window.
                
                # Randomly sample indices (skipping first 200 warmup)
                possible_indices = range(200, len(df))
                
                # If history is too short
                if len(possible_indices) < samples_per_coin:
                    continue
                    
                selected_indices = np.random.choice(
                    possible_indices, 
                    size=samples_per_coin, 
                    replace=False
                )
                
                for idx in selected_indices:
                    # Context window for feature calculation (200 bars is enough for RSI/EMA warmup)
                    start_idx = idx - 200
                    context = df.iloc[start_idx : idx + 1].copy()
                    
                    # Extract features on small window
                    # This is 350x faster than extracting whole history (200 vs 70000 rows)
                    feats_window = extract_all_features(context)
                    
                    # Take the last row (our target sample)
                    feat_vector = feats_window.iloc[-1]
                    
                    # FIX: Remove non-feature columns (Same as prepare_dataset)
                    cols_to_drop = [
                        'open', 'high', 'low', 'close', 'volume', 
                        'open_time', 'close_time', 'timestamp', 'datetime',
                        'symbol', 'timeframe'
                    ]
                    # Drop existing only
                    feat_vector = feat_vector.drop(labels=[c for c in cols_to_drop if c in feat_vector.index])
                    
                    neg_features_list.append(feat_vector)
                    
                if len(neg_features_list) >= count:
                    break
                    
            except Exception as e:
                logger.warning(f"Error sampling negatives from {symbol}: {e}")
                continue
        
        # Create DataFrame
        if not neg_features_list:
            logger.warning("Failed to generate negative samples!")
            return pd.DataFrame(), pd.Series()
            
        # Limit to count
        neg_features_list = neg_features_list[:count]
        
        X_neg = pd.DataFrame(neg_features_list)
        y_neg = pd.Series([0] * len(neg_features_list)) # Label 0 = Failure/Noise
        
    
        logger.info(f"Generated {len(X_neg)} negative samples")
        return X_neg, y_neg

    def generate_hard_negative_samples(self, negatives_path: str) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Load specific 'Hard Negative' samples (False Positives from backtest) 
        for Active Learning.
        """
        path = Path(negatives_path)
        if not path.exists():
            logger.warning(f"Hard negatives file not found: {path}")
            return pd.DataFrame(), pd.Series()
            
        with open(path, 'r') as f:
            negatives = json.load(f)
            
        if not negatives:
            return pd.DataFrame(), pd.Series()
            
        logger.info(f"Loading {len(negatives)} hard negatives...")
        
        features_list = []
        
        # Group by symbol to minimize IO
        from collections import defaultdict
        grouped = defaultdict(list)
        for n in negatives:
            grouped[n['symbol']].append(n)
            
        for symbol, items in grouped.items():
            # Load History
            # Assuming 15m for now as per miner
            history_path = get_history_file(symbol, "15m")
            if not history_path.exists():
                logger.warning(f"History not found for {symbol}")
                continue
                
            try:
                df = pd.read_parquet(history_path)
                # Ensure datetime
                if 'open_time' in df.columns:
                     if df['open_time'].dtype == object:
                        df['open_time'] = pd.to_datetime(df['open_time'])
                
                # Extract all features (vectorized)
                # We need full features to match training data
                df_feats = extract_all_features(df)
                
                # set index for fast lookup
                df_feats = df_feats.set_index('open_time')
                
                for item in items:
                    ts_str = item['timestamp']
                    ts = pd.to_datetime(ts_str)
                    
                    if ts in df_feats.index:
                        feat_vector = df_feats.loc[ts]
                        
                        # Drop non-feature columns
                        cols_to_drop = [
                            'open', 'high', 'low', 'close', 'volume', 
                            'open_time', 'close_time', 'timestamp', 'datetime', 'symbol', 'timeframe'
                        ]
                        # Drop existing only (handle Series vs DataFrame)
                        # feat_vector is a Series
                        feat_vector = feat_vector.drop(labels=[c for c in cols_to_drop if c in feat_vector.index])
                                
                        features_list.append(feat_vector)
                    else:
                        pass
                        
            except Exception as e:
                logger.error(f"Error processing hard negatives for {symbol}: {e}")
                
        if not features_list:
            return pd.DataFrame(), pd.Series()
            
        logger.info(f"Successfully extracted {len(features_list)} hard negative feature vectors.")
        return pd.DataFrame(features_list), pd.Series([0] * len(features_list))

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
                
                # FIX: Remove non-feature columns to prevent leakage
                # The model should not learn "Price was 50000" or "Date was 2023"
                cols_to_drop = [
                    'open', 'high', 'low', 'close', 'volume', 
                    'open_time', 'close_time', 'timestamp', 'datetime',
                    'symbol', 'timeframe'
                ]
                # Drop existing only
                feature_vector = feature_vector.drop(labels=[c for c in cols_to_drop if c in feature_vector.index])
                
                # Label: Success if gain > tier threshold
                # TODO: Define proper success criteria
                raw_data = rally.get('raw_data') or {}
                gain = raw_data.get('future_max_gain_pct', 0)
                
                # Simple threshold: >5% = success
                # FIX: Raw gain is decimal (0.05 = 5%), not scaled (5.0)
                # Since these ARE approved rallies, we treat them as POSITIVE (1) by default
                # unless they were failed rallies?
                # User says "Only successful". So label is 1.
                label = 1 
                
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
        timeframe: str = "15m",
        hard_negatives_path: Optional[str] = None
    ) -> Dict:
        """
        Generate Master Cipher for given filters.
        
        Args:
            tier: Target tier
            archetype: Target archetype
            coin_class: Target coin class
            timeframe: Target timeframe
            hard_negatives_path: Path to hard negatives JSON (Active Learning)
            
        Returns:
            Master Cipher dictionary
        """
        logger.info("=" * 70)
        logger.info("MASTER CIPHER GENERATION")
        logger.info("=" * 70)
        logger.info(f"Target: tier={tier}, archetype={archetype}, class={coin_class}, tf={timeframe}")
        
        # 1. Load training data (Positive Samples)
        # Parse wildcards
        t_tier = tier if tier != "ANY" else None
        t_arch = archetype if archetype != "ANY" else None
        t_class = coin_class if coin_class != "ANY" else None
        
        rallies = self.load_training_rallies(
            tier=t_tier,
            archetype=t_arch,
            coin_class=t_class,
            timeframe=timeframe
        )
        
        if len(rallies) < 10:
            raise ValueError(f"Insufficient data: {len(rallies)} rallies")
        
        # 2. Prepare Positive Dataset
        X_pos, y_pos, rally_ids = self.prepare_dataset(rallies)
        
        # 3. Generate Negative Samples (Balanced Training)
        # We target 1:1 ratio (Balanced)
        X_neg, y_neg = self.generate_negative_samples(count=len(X_pos), timeframe=timeframe)
        
        # 3.5 Load Hard Negatives (Active Learning)
        X_hard, y_hard = pd.DataFrame(), pd.Series()
        if hard_negatives_path:
            logger.info(f"🧬 Active Learning: Loading Hard Negatives from {hard_negatives_path}")
            X_hard, y_hard = self.generate_hard_negative_samples(hard_negatives_path)
            
        
        # Combine Datasets
        parts_X = [X_pos, X_neg if not X_neg.empty else None, X_hard if not X_hard.empty else None]
        parts_y = [y_pos, y_neg if not X_neg.empty else None, y_hard if not y_hard.empty else None]
        
        # Filter None
        parts_X = [p for p in parts_X if p is not None]
        parts_y = [p for p in parts_y if p is not None]
        
        X = pd.concat(parts_X, ignore_index=True).fillna(0)
        y = pd.concat(parts_y, ignore_index=True)
            
        logger.info(f"Dataset Created: {len(X_pos)} Pos + {len(X_neg)} Random Neg + {len(X_hard)} Hard Neg = {len(X)} Total")
        
        
        # 4. Run mining algorithm
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
                "algorithm_used": self.algorithm,
                "active_learning": bool(hard_negatives_path)
            },
            
            "training_stats": {
                "rally_count": len(rallies),
                "positive_ratio": float(y.mean()),
                "feature_pool_size": len(X.columns),
                "hard_negatives": len(X_hard)
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
