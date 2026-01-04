"""
Rule Engine - Deneysel Analiz Laboratuvarı
==========================================

Bu modül, tarihsel veriler üzerinde "Neden-Sonuç" analizleri yaparak
belirli tetikleyicilerin (Trigger) başarı oranlarını (Outcome) hesaplar.

Core Components:
- OpportunityScanner: Geçmişteki olayları bulur.
- OutcomeAnalyzer: Olaydan sonraki performansı ölçer.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path

from tezaver.core.logging_utils import get_logger
from tezaver.core.coin_cell_paths import get_history_file
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct

logger = get_logger(__name__)

class RuleEngine:
    """
    Kural Analiz Motoru.
    Geçmiş veriyi tarayarak spesifik senaryoların istatistiklerini çıkarır.
    """
    
    def __init__(self):
        pass
        
    def scan_volume_supernova(
        self, 
        symbol: str, 
        timeframe: str = "15m",
        min_mult: float = 3.0,
        max_mult: float = 15.0,
        lookahead_bars: int = 30
    ) -> Dict[str, Any]:
        """
        Scan for 'Volume SuperNova' events: Volume > N * MA20_Volume.
        
        Args:
            symbol: Target symbol (e.g., BTCUSDT)
            timeframe: Timeframe (e.g., 15m)
            min_mult: Minimum volume multiplier (default 3x)
            max_mult: Maximum volume multiplier (default 15x) -> We scan range
            lookahead_bars: How many future bars to check for gain
            
        Returns:
            Dictionary containing stats per multiplier step.
        """
        logger.info(f"Scanning SuperNova for {symbol} {timeframe}...")
        
        # 1. Load History
        path = get_history_file(symbol, timeframe)
        if not path.exists():
            logger.warning(f"History not found for {symbol}")
            return {"error": "history_not_found"}
            
        df = pd.read_parquet(path)
        if len(df) < 200:
            return {"error": "insufficient_data"}
            
        # Ensure we have volume
        if 'volume' not in df.columns:
            return {"error": "missing_volume_column"}
            
        # 2. Calculate Indicators (Vectorized)
        # Volume MA 20
        df['vol_ma20'] = df['volume'].rolling(window=20).mean()
        
        # Avoid division by zero
        df['vol_ratio'] = df['volume'] / df['vol_ma20'].replace(0, 1)
        
        # 3. Scan for each multiplier step (3x, 4x, ... 15x)
        results = []
        
        # Range: 3, 4, 5, ..., 15 (inclusive)
        multipliers = list(range(int(min_mult), int(max_mult) + 1))
        
        for mult in multipliers:
            # Find events where Volume > mult * MA
            # Ensure we have enough lookahead
            mask = (df['vol_ratio'] >= mult)
            
            # Get indices
            indices = df.index[mask].tolist()
            
            # Filter indices that are too close to the end
            indices = [idx for idx in indices if idx < len(df) - lookahead_bars]
            
            # Analyze outcomes
            stats = self._analyze_outcomes(df, indices, lookahead_bars)
            stats['multiplier'] = mult
            results.append(stats)
            
        return {
            "symbol": symbol,
            "period": f"{df.index[0]} - {df.index[-1]}",
            "total_bars": len(df),
            "results": results
        }
        
    def _analyze_outcomes(self, df: pd.DataFrame, indices: List[Any], lookahead: int) -> Dict[str, Any]:
        """
        Analyze what happened after the events.
        """
        if not indices:
            return {
                "count": 0,
                "tiers": {"DIAMOND": 0, "GOLD": 0, "SILVER": 0, "BRONZE": 0, "IRON": 0, "NEGATIVE": 0},
                "avg_gain": 0.0,
                "win_rate": 0.0
            }
            
        outcomes = []
        
        # Use integer location for speed
        # Convert index labels to integer positions if needed
        # Assuming Index is DatetimeIndex, we need get_loc or reset_index
        # For speed on large df, standard RangeIndex is best. Let's use iloc logic.
        
        # Optimization: Reset index to work with 0..N integers
        # Only do this once if possible, but here we do it locally
        df_reset = df.reset_index(drop=True)
        # Map original indices to new integer indices (if they weren't ints)
        # But indices from df.index[mask] match df's index. 
        # CAUTION: 'indices' list currently holds values from df.index.
        # If df has DatetimeIndex, these are timestamps.
        
        # Let's re-find integer locations
        # Better approach: work with numpy arrays
        close_arr = df_reset['close'].values
        
        # Convert indices to integer positions
        # df.index.get_indexer(indices) is fast for DatetimeIndex
        if isinstance(df.index, pd.DatetimeIndex):
             int_indices = df.index.get_indexer(indices)
        else:
             int_indices = indices # Assuming already int if RangeIndex
             
        # Initialize counters for all symmetric tiers
        # Format: POS_DIAMOND, NEG_DIAMOND, etc.
        tiers_count = {
            "POS_DIAMOND": 0, "POS_GOLD": 0, "POS_SILVER": 0, "POS_BRONZE": 0, "POS_IRON": 0,
            "NEG_DIAMOND": 0, "NEG_GOLD": 0, "NEG_SILVER": 0, "NEG_BRONZE": 0, "NEG_IRON": 0,
        }
        
        total_gain = 0.0
        wins = 0
        
        for idx in int_indices:
            if idx < 0: continue
            
            entry_price = close_arr[idx]
            
            # Lookahead window
            end_idx = min(idx + lookahead, len(close_arr))
            window = close_arr[idx+1 : end_idx+1]
            
            if len(window) == 0:
                continue
                
            # For simplistic "Outcome", we usually look at max gain for Long logic.
            # But the user wants breakdown of what happened.
            # Ideally: Did it hit a stop loss? Did it hit a profit?
            # For this "SuperNova" raw analysis, let's look at the FINAL outcome after N bars 
            # OR the Max Excursion. 
            # "Cause and effect": If volume spikes, does price go UP or DOWN?
            # Let's take the Price Change at the end of N bars (Simple Return)
            # OR Max Gain vs Max Loss?
            # Users request implies a distribution. Usually we classify by Max Gain if bullish.
            # But if it crashes, we classify by Max Loss?
            # Let's use: Return after N bars. Or better:
            # - If Max Gain > Threshold -> It's a Bullish Tier
            # - If Max Loss < Threshold (and gain didn't hit) -> Bearish Tier?
            # Simpler approach for "Auditor": 
            # Check price change at the END of window (or max potential).
            # Let's stick to "Max Potential Gain" for Positives and "Max Drawdown" for Negatives?
            # PROBLEM: Every candle has both drawdown and gain.
            # DECISION: Let's use the CLOSE price at t+N vs Entry. This is the "Net Result".
            
            exit_price = window[-1] # Price at end of N bars
            gain_pct = (exit_price - entry_price) / entry_price
            
            abs_gain = abs(gain_pct)
            tier_name = compute_tier_from_gain_pct(abs_gain)
            
            if tier_name is None: 
                # Should not happen since IRON covers 0-5%. 
                # If abs_gain < 0 (impossible) or NaN.
                # If 0%, it maps to IRON.
                tier_name = "IRON" 
                
            if gain_pct >= 0:
                key = f"POS_{tier_name}"
                wins += 1
            else:
                key = f"NEG_{tier_name}"
                
            if key in tiers_count:
                tiers_count[key] += 1
                
            total_gain += gain_pct
            
        count = len(int_indices)
        return {
            "count": count,
            "tiers": tiers_count,
            "avg_gain": (total_gain / count) if count > 0 else 0.0,
            "win_rate": (wins / count) if count > 0 else 0.0
        }
