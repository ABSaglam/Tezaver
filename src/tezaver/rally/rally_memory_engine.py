"""
Rally Memory Engine
====================

Bu modül, BTCUSDT 15 Dakika rally'leri için "Rally Context Score" hesaplar.
Hesaplama, önceden belirlenmiş "tatlı bölge" (sweet spot) aralıklarına dayanır.

Rally Context Score v1:
- rsi_15m, volume_rel_15m, atr_pct_15m metriklerini değerlendirir
- Her metrik için: içeride=1.0, soft margin=0.5, dışarıda=0.0
- Toplam skor: normalize edilmiş 0-100 arası değer
"""

from dataclasses import dataclass
from typing import Optional
import pandas as pd
import numpy as np


# =============================================================================
# SWEET SPOT YAPILARI
# =============================================================================

@dataclass
class SweetSpotRange:
    """Tek bir metrik için tatlı bölge tanımı."""
    lower: float      # Alt sınır
    upper: float      # Üst sınır
    soft_margin: float  # Dış kenar bant genişliği


@dataclass
class Btc15mSweetSpotConfig:
    """BTCUSDT 15 Dakika için tüm tatlı bölge konfigürasyonu."""
    rsi_15m: SweetSpotRange
    volume_rel_15m: SweetSpotRange
    atr_pct_15m: SweetSpotRange


# =============================================================================
# DEFAULT KONFİGÜRASYON
# =============================================================================

DEFAULT_BTCUSDT_15M_SWEET_SPOTS = Btc15mSweetSpotConfig(
    rsi_15m=SweetSpotRange(lower=22.4, upper=41.0, soft_margin=5.0),
    volume_rel_15m=SweetSpotRange(lower=1.96, upper=2.31, soft_margin=0.3),
    atr_pct_15m=SweetSpotRange(lower=0.61, upper=1.54, soft_margin=0.3),
)


# =============================================================================
# SKOR HESAPLAMA FONKSİYONLARI
# =============================================================================

def compute_metric_match_score(
    x: Optional[float],
    sweet_spot: SweetSpotRange,
) -> float:
    """
    Tek bir metrik için tatlı bölge eşleşme skoru hesaplar.
    
    Args:
        x: Metrik değeri (None veya NaN olabilir)
        sweet_spot: Tatlı bölge tanımı
        
    Returns:
        1.0: Değer [lower, upper] aralığında (içeride)
        0.5: Değer soft margin içinde (kenar bölge)
        0.0: Değer tamamen dışarıda veya None/NaN
    """
    # None veya NaN kontrolü
    if x is None:
        return 0.0
    if isinstance(x, float) and np.isnan(x):
        return 0.0
    
    L = sweet_spot.lower
    U = sweet_spot.upper
    delta = sweet_spot.soft_margin
    
    # İçeride mi?
    if L <= x <= U:
        return 1.0
    
    # Soft margin içinde mi?
    # Alt kenar: L - delta <= x < L
    if L - delta <= x < L:
        return 0.5
    
    # Üst kenar: U < x <= U + delta
    if U < x <= U + delta:
        return 0.5
    
    # Tamamen dışarıda
    return 0.0


def compute_rally_context_score_v1_for_row(
    row,
    config: Btc15mSweetSpotConfig = None,
) -> float:
    """
    Tek bir rally satırı için BTCUSDT 15m Rally Context Score v1 hesaplar.
    
    Args:
        row: pandas Series veya dict-like obje (rsi_15m, volume_rel_15m, atr_pct_15m içermeli)
        config: Tatlı bölge konfigürasyonu (default: DEFAULT_BTCUSDT_15M_SWEET_SPOTS)
        
    Returns:
        0-100 arasında normalize edilmiş skor
    """
    if config is None:
        config = DEFAULT_BTCUSDT_15M_SWEET_SPOTS
    
    # Metrikleri oku (güvenli şekilde)
    rsi = row.get("rsi_15m") if hasattr(row, "get") else row.get("rsi_15m", None)
    volume = row.get("volume_rel_15m") if hasattr(row, "get") else row.get("volume_rel_15m", None)
    atr = row.get("atr_pct_15m") if hasattr(row, "get") else row.get("atr_pct_15m", None)
    
    # Her metrik için skor hesapla
    score_rsi = compute_metric_match_score(rsi, config.rsi_15m)
    score_volume = compute_metric_match_score(volume, config.volume_rel_15m)
    score_atr = compute_metric_match_score(atr, config.atr_pct_15m)
    
    metric_scores = [score_rsi, score_volume, score_atr]
    
    # Toplam ve normalize
    raw_score = sum(metric_scores)
    max_score = len(metric_scores)  # 3
    
    if max_score == 0:
        return 0.0
    
    normalized = (raw_score / max_score) * 100.0
    
    return float(normalized)


def add_rally_context_score_v1_column(
    df: pd.DataFrame,
    config: Btc15mSweetSpotConfig = None,
    column_name: str = "rally_context_score_v1",
) -> pd.DataFrame:
    """
    DataFrame'e Rally Context Score v1 kolonu ekler.
    
    Args:
        df: Rally event'lerini içeren DataFrame
        config: Tatlı bölge konfigürasyonu (default: DEFAULT_BTCUSDT_15M_SWEET_SPOTS)
        column_name: Yeni kolonun adı
        
    Returns:
        Yeni kolon eklenmiş DataFrame kopyası
    """
    if config is None:
        config = DEFAULT_BTCUSDT_15M_SWEET_SPOTS
    
    df_copy = df.copy()
    
    # Apply fonksiyonu ile satır satır hesapla
    df_copy[column_name] = df_copy.apply(
        lambda row: compute_rally_context_score_v1_for_row(row, config),
        axis=1
    )
    
    return df_copy
