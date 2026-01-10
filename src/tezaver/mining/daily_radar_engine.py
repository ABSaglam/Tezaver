"""
GEN-RADAR Engine - Multi-Timeframe DNA Filter
=============================================
Filters coins using:
1. Character DNA (Definitive 10-Tier)
2. Daily (1D) Structure: ATR%, Price vs Midpoint, Green candles
3. 4H Momentum: RSI trend, MACD histogram
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from tezaver.core import config, coin_cell_paths
from tezaver.data.history_service import bulk_update_history


@dataclass
class DailyMetrics:
    """Daily structure metrics for a coin."""
    symbol: str
    atr_pct: float       # ATR as % of price
    midpoint_pct: float  # Close position within 5-day range (0-100%)
    green_days: int      # Number of green days in last 3
    bb_squeeze: bool     # Bollinger Band squeeze active
    near_resistance: bool # Close within 2% of 5-day high
    

@dataclass
class MomentumMetrics:
    """4H momentum metrics for a coin."""
    rsi: float
    rsi_rising: bool     # RSI increased over last 6 bars
    macd_positive: bool  # MACD histogram > 0
    macd_rising: bool    # MACD histogram increasing
    green_bars: int      # Green bars in last 3
    

@dataclass
class RadarResult:
    """Final radar result for a coin."""
    symbol: str
    category: str        # "BREAKOUT" or "TREND" or "WATCH" or "AMBUSH"
    daily: DailyMetrics
    momentum: MomentumMetrics
    score: int           # Composite score 0-100
    dna_tier: str = "N/A" # DNA Tier from coin_dna_definitive.json
    dna_score: float = 0.0
    

class DailyRadarEngine:
    """Main engine for Daily Radar filtering."""
    
    def __init__(self):
        self.coins = config.DEFAULT_COINS
        self.dna_profiles = self._load_dna_profiles()
        
    def _load_dna_profiles(self) -> Dict[str, Dict]:
        """Load definitive DNA profiles."""
        try:
            import json
            import os
            path = "library/coin_dna_definitive.json"
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    return {p['symbol']: p for p in data}
        except Exception:
            pass
        return {}

    def sync_data(self, timeframes: List[str] = ["1d", "4h"], fast_only: bool = True):
        """Synchronize historical data for all coins."""
        bulk_update_history(self.coins, timeframes, fast_only=fast_only)
        
    def calculate_daily_structure(self, df: pd.DataFrame) -> Optional[DailyMetrics]:
        """Calculate daily structure metrics."""
        if df is None or len(df) < 20:
            return None
            
        try:
            # ATR%
            df['tr'] = np.maximum(
                df['high'] - df['low'],
                np.maximum(
                    abs(df['high'] - df['close'].shift(1)),
                    abs(df['low'] - df['close'].shift(1))
                )
            )
            atr = df['tr'].rolling(14).mean().iloc[-1]
            atr_pct = (atr / df['close'].iloc[-1]) * 100
            
            # Position within 5-day range
            high_5d = df['high'].tail(5).max()
            low_5d = df['low'].tail(5).min()
            range_5d = high_5d - low_5d
            if range_5d > 0:
                midpoint_pct = ((df['close'].iloc[-1] - low_5d) / range_5d) * 100
            else:
                midpoint_pct = 50.0
                
            # Green days
            df['green'] = df['close'] > df['open']
            green_days = df['green'].tail(3).sum()
            
            # BB Squeeze (BB Width < 20-day low)
            df['sma20'] = df['close'].rolling(20).mean()
            df['std20'] = df['close'].rolling(20).std()
            df['bb_width'] = (df['std20'] * 4) / df['sma20'] * 100
            bb_width_now = df['bb_width'].iloc[-1]
            bb_width_min = df['bb_width'].tail(20).min()
            bb_squeeze = bb_width_now <= bb_width_min * 1.1  # Within 10% of min
            
            # Near resistance
            near_resistance = (high_5d - df['close'].iloc[-1]) / df['close'].iloc[-1] < 0.02
            
            return DailyMetrics(
                symbol="",  # Filled by caller
                atr_pct=atr_pct,
                midpoint_pct=midpoint_pct,
                green_days=int(green_days),
                bb_squeeze=bb_squeeze,
                near_resistance=near_resistance
            )
        except Exception:
            return None
            
    def calculate_4h_momentum(self, df: pd.DataFrame) -> Optional[MomentumMetrics]:
        """Calculate 4H momentum metrics."""
        if df is None or len(df) < 30:
            return None
            
        try:
            # RSI
            delta = df['close'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            rs = up.ewm(com=13, adjust=False).mean() / down.ewm(com=13, adjust=False).mean()
            df['rsi'] = 100 - (100 / (1 + rs))
            
            rsi_now = df['rsi'].iloc[-1]
            rsi_6_ago = df['rsi'].iloc[-7] if len(df) >= 7 else df['rsi'].iloc[0]
            rsi_rising = rsi_now > rsi_6_ago
            
            # MACD
            ema12 = df['close'].ewm(span=12, adjust=False).mean()
            ema26 = df['close'].ewm(span=26, adjust=False).mean()
            macd_line = ema12 - ema26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            df['macd_hist'] = macd_line - signal_line
            
            macd_positive = df['macd_hist'].iloc[-1] > 0
            macd_rising = df['macd_hist'].iloc[-1] > df['macd_hist'].iloc[-4]
            
            # Green bars
            df['green'] = df['close'] > df['open']
            green_bars = df['green'].tail(3).sum()
            
            return MomentumMetrics(
                rsi=rsi_now,
                rsi_rising=rsi_rising,
                macd_positive=macd_positive,
                macd_rising=macd_rising,
                green_bars=int(green_bars)
            )
        except Exception:
            return None
            
    def passes_daily_filter(self, metrics: DailyMetrics, dna: Dict) -> bool:
        """Check if coin passes daily structure filter with tier-aware thresholds."""
        tier = dna.get('tier', 'C')
        
        # D/F Tiers are automatically rejected
        if tier in ['D', 'F']:
            return False
            
        # ATR% Thresholds
        min_atr = 2.0
        if tier in ['S', 'A']: min_atr = 1.5  # More lenient for elite coins
        if tier in ['C+', 'C', 'C-']: min_atr = 2.5 # Stricter for risky coins
        
        if metrics.atr_pct < min_atr:
            return False
            
        # Price position (midpoint)
        min_mid = 40
        if tier in ['S', 'A']: min_mid = 40 
        if tier in ['B+']: min_mid = 70 
        if tier in ['B']: min_mid = 85
        if tier in ['B-', 'C+', 'C', 'C-']: min_mid = 90
        
        if metrics.midpoint_pct < min_mid:
            return False
            
        # Green days
        if metrics.green_days < 1:
            return False
            
        return True
        
    def passes_momentum_filter(self, metrics: MomentumMetrics, dna: Dict) -> bool:
        """Check if coin passes 4H momentum filter with tier-aware thresholds."""
        tier = dna.get('tier', 'C')
        
        # RSI Thresholds
        min_rsi = 45
        if tier in ['S', 'A']: min_rsi = 40
        if tier in ['B+']: min_rsi = 60
        if tier in ['B']: min_rsi = 70
        if tier in ['B-', 'C+', 'C', 'C-']: min_rsi = 75
        
        if metrics.rsi < min_rsi:
            return False
            
        # Directional requirement
        if tier in ['S', 'A', 'B+']:
            # RSI rising OR MACD rising
            if not (metrics.rsi_rising or metrics.macd_rising):
                return False
        else:
            # Stricter for C-tier: Both must be rising
            if not (metrics.rsi_rising and metrics.macd_rising):
                return False
                
        if metrics.green_bars < 1:
            return False
            
        return True

    def is_ninja_candidate(self, daily: DailyMetrics, momentum: MomentumMetrics, dna: Dict) -> bool:
        """
        Detect potential explosive 'NINJA' moves from the bottom.
        Focuses on high-volatility coins in a squeeze.
        """
        vol_rank = dna.get('vol_rank', 0)
        # 1. High DNA Volatility (Top 30% of volatile coins)
        if vol_rank < 70:
            return False
            
        # 2. Bottom/Middle Position (Not already at the top)
        if daily.midpoint_pct > 60:
            return False
            
        # 3. Squeeze presence
        # If ultra-high vol, be more lenient on the squeeze
        if vol_rank > 85:
            if not daily.bb_squeeze:
                # Still check if it's at least not expanding (weak squeeze)
                # (This is a simplified check for the backtest script logic)
                pass 
        else:
            if not daily.bb_squeeze:
                return False
            
        # 4. Early Momentum: 4H RSI crossing 45 OR MACD Rising
        if momentum.rsi < 40 or not momentum.macd_rising:
            return False
            
        return True
        
    def is_ambush_candidate(self, daily: DailyMetrics, momentum: MomentumMetrics, dna: Dict) -> bool:
        """
        Identify coins poised for a breakout (The Pusu Metric).
        - High DNA Tier (B or higher)
        - Tight Bollinger Band Squeeze
        - Low-to-Mid price position (Midpoint 15-55%)
        - Early 4H Momentum (RSI 40-60)
        """
        # Tier check
        tier_rank = {'S': 5, 'A': 4, 'B+': 3, 'B': 2, 'B-': 1, 'C+': 0, 'C': -1, 'C-': -2, 'D': -3, 'E': -4}
        if tier_rank.get(dna.get('tier'), -10) < tier_rank.get('B', 0):
            return False
            
        # Squeeze check
        if not daily.bb_squeeze:
            return False
            
        # Midpoint check (not over-extended)
        if not (15 <= daily.midpoint_pct <= 55):
            return False
            
        # Momentum check (not fully erupted yet, but ready)
        if not (40 <= momentum.rsi <= 60):
            return False
            
        return True

    def categorize(self, daily: DailyMetrics, momentum: MomentumMetrics, dna: Dict) -> str:
        """Categorize coin into a radar category."""
        # 1. Check for NINJA (bottom reversal)
        if self.is_ninja_candidate(daily, momentum, dna):
            return "NINJA"
            
        # 2. Check for TREND (continuation)
        if self.passes_daily_filter(daily, dna) and self.passes_momentum_filter(momentum, dna):
            return "TREND"
            
        # 3. Check for AMBUSH (coiled for breakout)
        if self.is_ambush_candidate(daily, momentum, dna):
            return "AMBUSH"
            
        # 4. Check for BREAKOUT (near resistance)
        if daily.near_resistance and momentum.rsi > 60:
            return "BREAKOUT"
            
        return "WATCH"
        
    def calculate_score(self, daily: DailyMetrics, momentum: MomentumMetrics) -> int:
        """Calculate composite score (0-100)."""
        score = 0
        # Daily structure
        score += min(20, int(daily.atr_pct * 5))  # Up to 20 for volatility
        score += int(daily.midpoint_pct * 0.2)   # Up to 20 for position
        score += daily.green_days * 5            # Up to 15 for green days
        if daily.bb_squeeze: score += 10
        if daily.near_resistance: score += 5
        # Momentum
        score += min(15, int((momentum.rsi - 45) * 0.5)) if momentum.rsi > 45 else 0
        if momentum.rsi_rising: score += 5
        if momentum.macd_positive: score += 5
        if momentum.macd_rising: score += 5
        score += momentum.green_bars * 3
        return min(100, score)
        
    def scan_all(self, progress_callback=None, refresh_data=False) -> List[RadarResult]:
        """Scan all coins for radar signals."""
        if refresh_data:
            # Automatic sync before scan
            self.sync_data(timeframes=["1d", "4h"], fast_only=True)
            
        results = []
        total = len(self.coins)
        
        for i, symbol in enumerate(self.coins):
            if progress_callback:
                progress_callback(i, total, symbol)
                
            try:
                # Load daily data
                path_1d = coin_cell_paths.get_history_file(symbol, "1d")
                if not path_1d.exists():
                    continue
                df_1d = pd.read_parquet(path_1d)
                
                # Load 4H data
                path_4h = coin_cell_paths.get_history_file(symbol, "4h")
                if not path_4h.exists():
                    continue
                df_4h = pd.read_parquet(path_4h)
                
                # DNA Profile
                dna = self.dna_profiles.get(symbol, {
                    "tier": "C", 
                    "composite": 50.0, 
                    "vol_rank": 50.0,
                    "is_default": True
                })
                
                # Calculate metrics
                daily = self.calculate_daily_structure(df_1d)
                if daily is None:
                    continue
                daily.symbol = symbol

                momentum = self.calculate_4h_momentum(df_4h)
                if momentum is None:
                    continue
                    
                # Special Pass: Even if it fails normal DAILY/MOMENTUM filters (which are trend-following),
                # it might be a valid NINJA candidate.
                is_ninja = self.is_ninja_candidate(daily, momentum, dna)
                
                if not is_ninja:
                    # Ambush check
                    is_ambush = self.is_ambush_candidate(daily, momentum, dna)
                    
                    if not is_ambush:
                        # Normal trend filters
                        if not self.passes_daily_filter(daily, dna):
                            continue
                        if not self.passes_momentum_filter(momentum, dna):
                            continue
                    
                # Passed all filters
                category = self.categorize(daily, momentum, dna)
                score = self.calculate_score(daily, momentum)
                
                # DNA Bonus
                tier_bonuses = {'S': 20, 'A': 15, 'B+': 10, 'B': 5, 'B-': 2}
                score += tier_bonuses.get(dna.get('tier'), 0)
                score = min(100, score)
                
                results.append(RadarResult(
                    symbol=symbol,
                    category=category,
                    daily=daily,
                    momentum=momentum,
                    score=score,
                    dna_tier=dna.get('tier', 'N/A'),
                    dna_score=dna.get('composite', 0.0)
                ))
                
            except Exception:
                continue
                
        # Sort by score
        results.sort(key=lambda x: x.score, reverse=True)
        return results
