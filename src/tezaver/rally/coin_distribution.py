"""
Coin Distribution Analyzer - Her Coin İçin Rally Distribution'u Hesapla

Her coinin kendi rally karakteristiğini (percentile'lar, volatilite profili)
hesaplar ve saklar. Böylece coin-specific grading yapılabilir.

Örnek:
- BTCUSDT: p99 = %22 (Diamond eşiği)
- DOGEUSDT: p99 = %50 (Diamond eşiği)
"""

import pandas as pd
import numpy as np
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from tezaver.core.logging_utils import get_logger
from tezaver.core.coin_cell_paths import get_coin_profile_dir


logger = get_logger(__name__)


class CoinDistributionAnalyzer:
    """
    Her coin için rally distribution hesapla ve sakla.
    """
    
    def __init__(self):
        self.logger = logger
    
    def compute_distribution(self, symbol: str, rallies_df: pd.DataFrame) -> Dict:
        """
        Coin için distribution hesapla.
        
        Args:
            symbol: Coin symbolu (örn: BTCUSDT)
            rallies_df: Rally dataframe (true_gain_pct gerekli)
        
        Returns:
            Distribution dictionary
        """
        
        if len(rallies_df) < 10:
            self.logger.warning(f"{symbol}: Yetersiz rally ({len(rallies_df)}), default distribution kullanılacak")
            return self._get_default_distribution(symbol)
        
        # Gain percentiles
        gain_col = 'true_gain_pct' if 'true_gain_pct' in rallies_df.columns else 'future_max_gain_pct'
        gains = rallies_df[gain_col].dropna()
        
        gain_percentiles = {
            'p50': float(np.percentile(gains, 50)),
            'p70': float(np.percentile(gains, 70)),
            'p80': float(np.percentile(gains, 80)),
            'p90': float(np.percentile(gains, 90)),
            'p95': float(np.percentile(gains, 95)),
            'p99': float(np.percentile(gains, 99)),
        }
        
        # Duration percentiles
        if 'bars_duration' in rallies_df.columns:
            durations = rallies_df['bars_duration'].dropna()
            duration_percentiles = {
                'p50': float(np.percentile(durations, 50)),
                'p90': float(np.percentile(durations, 90)),
            }
        else:
            duration_percentiles = {'p50': 12, 'p90': 25}
        
        # Volatility profile (pullback tolerance)
        if 'pre_peak_drawdown_pct' in rallies_df.columns:
            drawdowns = rallies_df['pre_peak_drawdown_pct'].dropna()
            typical_pullback = float(drawdowns.median())
            max_pullback_clean = float(np.percentile(drawdowns, 70))  # 70th percentile = "clean" threshold
        else:
            typical_pullback = 0.02  # 2% default
            max_pullback_clean = 0.03  # 3% default
        
        distribution = {
            'symbol': symbol,
            'last_updated': datetime.now().isoformat(),
            'total_rallies': len(rallies_df),
            'gain_percentiles': gain_percentiles,
            'duration_percentiles': duration_percentiles,
            'volatility_profile': {
                'typical_pullback': typical_pullback,
                'max_pullback_clean': max_pullback_clean,
                'max_pullback_choppy': max_pullback_clean * 2.0,  # 2x for choppy
            },
            'quality_stats': {
                'avg_quality': float(rallies_df['quality_score'].mean()) if 'quality_score' in rallies_df.columns else 70.0,
                'avg_momentum': float(rallies_df['momentum_score'].mean()) if 'momentum_score' in rallies_df.columns else 0.3,
            }
        }
        
        self.logger.info(f"{symbol} distribution hesaplandı: Diamond≥{gain_percentiles['p99']*100:.1f}%")
        return distribution
    
    def save_distribution(self, symbol: str, distribution: Dict) -> Path:
        """
        Distribution'u JSON olarak kaydet.
        
        Path: data/coin_profiles/{SYMBOL}/rally_distribution.json
        """
        profile_dir = get_coin_profile_dir(symbol)
        output_path = profile_dir / "rally_distribution.json"
        
        # Ensure directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(distribution, f, indent=2)
        
        self.logger.info(f"{symbol} distribution kaydedildi: {output_path}")
        return output_path
    
    def load_distribution(self, symbol: str) -> Optional[Dict]:
        """
        Distribution'u JSON'dan yükle.
        
        Returns:
            Distribution dict veya None (yoksa)
        """
        profile_dir = get_coin_profile_dir(symbol)
        dist_path = profile_dir / "rally_distribution.json"
        
        if not dist_path.exists():
            self.logger.debug(f"{symbol} distribution bulunamadı: {dist_path}")
            return None
        
        try:
            with open(dist_path, 'r') as f:
                distribution = json.load(f)
            
            self.logger.debug(f"{symbol} distribution yüklendi")
            return distribution
        
        except Exception as e:
            self.logger.error(f"{symbol} distribution yüklenemedi: {e}")
            return None
    
    def load_or_default(self, symbol: str) -> Dict:
        """
        Distribution yükle, yoksa default kullan.
        """
        dist = self.load_distribution(symbol)
        if dist is None:
            self.logger.warning(f"{symbol} distribution yok, default kullanılıyor")
            return self._get_default_distribution(symbol)
        return dist
    
    def _get_default_distribution(self, symbol: str) -> Dict:
        """
        Default distribution (coin taranmamışsa).
        
        Genel kripto market için orta seviye değerler.
        """
        return {
            'symbol': symbol,
            'last_updated': datetime.now().isoformat(),
            'total_rallies': 0,
            'gain_percentiles': {
                'p50': 0.07,   # %7
                'p70': 0.10,   # %10
                'p80': 0.13,   # %13
                'p90': 0.17,   # %17
                'p95': 0.22,   # %22
                'p99': 0.35,   # %35
            },
            'duration_percentiles': {
                'p50': 12,
                'p90': 25,
            },
            'volatility_profile': {
                'typical_pullback': 0.025,
                'max_pullback_clean': 0.03,
                'max_pullback_choppy': 0.06,
            },
            'quality_stats': {
                'avg_quality': 70.0,
                'avg_momentum': 0.3,
            }
        }


def grade_rally_percentile(rally_gain_pct: float, symbol: str, distribution: Optional[Dict] = None) -> str:
    """
    Rally'i coin distribution'una göre grade'le.
    
    Args:
        rally_gain_pct: Rally kazancı (örn: 0.15 = %15)
        symbol: Coin symbolu
        distribution: Distribution dict (None ise yüklenecek)
    
    Returns:
        Grade: "💎 Diamond", "🥇 Gold", "🥈 Silver", "🥉 Bronze"
    """
    
    if distribution is None:
        analyzer = CoinDistributionAnalyzer()
        distribution = analyzer.load_or_default(symbol)
    
    percentiles = distribution['gain_percentiles']
    
    # Percentile-based grading
    if rally_gain_pct >= percentiles['p99']:
        return "💎 Diamond"  # Top %1
    elif rally_gain_pct >= percentiles['p90']:
        return "🥇 Gold"     # Top %10
    elif rally_gain_pct >= percentiles['p70']:
        return "🥈 Silver"   # Top %30
    else:
        return "🥉 Bronze"   # Below top %30


def get_coin_quality_config(symbol: str, distribution: Optional[Dict] = None) -> Dict:
    """
    Coin-specific quality scoring config.
    
    Volatility profile'a göre shape score thresholds.
    """
    
    if distribution is None:
        analyzer = CoinDistributionAnalyzer()
        distribution = analyzer.load_or_default(symbol)
    
    vol_profile = distribution['volatility_profile']
    
    return {
        'clean_pullback_threshold': vol_profile['max_pullback_clean'],
        'choppy_pullback_threshold': vol_profile['max_pullback_choppy'],
        'typical_pullback': vol_profile['typical_pullback'],
    }
