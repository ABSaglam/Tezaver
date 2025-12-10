"""
Rally Start Detector - Gerçek Rally Başlangıç Barını Tespit Et

Tepeden geriye giderek rally'nin gerçek başlangıç noktasını bulur.
Böylece kazanç hesabı doğru base'den yapılır.

Algoritma:
1. Peak'ten geriye git (max 50 bar)
2. Local minimum bul (pullback tolerance ile)
3. Momentum confirmation (MACD, RSI turning point)
4. Volume confirmation (düşük hacimden yüksek hacme geçiş)
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from datetime import datetime

from tezaver.core.logging_utils import get_logger

logger = get_logger(__name__)


def find_true_rally_start(
    df: pd.DataFrame,
    peak_idx: int,
    peak_price: float,
    max_lookback: int = 50,
    pullback_tolerance: float = 0.03
) -> Dict:
    """
    Tepeden geriye giderek gerçek rally start barını bul.
    
    Args:
        df: OHLCV dataframe (timestamp indexed veya 'timestamp' column)
        peak_idx: Peak barının index'i
        peak_price: Peak fiyatı
        max_lookback: Maksimum geriye bakış (bar sayısı)
        pullback_tolerance: Pullback toleransı (3% = 0.03)
    
    Returns:
        {
            'rally_start_idx': int,
            'rally_start_price': float,
            'rally_start_time': datetime,
            'true_gain_pct': float,
            'bars_duration': int,
            'confidence': float,
            'method': str  # 'local_minimum', 'momentum_turn', 'volume_surge'
        }
    """
    
    # Peak'ten önceki veriyi al
    start_search_idx = max(0, peak_idx - max_lookback)
    search_window = df.iloc[start_search_idx:peak_idx + 1].copy()
    
    if len(search_window) < 3:
        # Çok az veri, peak'i start olarak kullan
        logger.warning(f"Yetersiz veri, peak_idx={peak_idx} start olarak kullanılıyor")
        return _create_fallback_result(df, peak_idx, peak_price)
    
    # Stratejiler
    candidates = []
    
    # Strateji 1: Local Minimum (En düşük fiyat)
    local_min_result = _find_local_minimum(search_window, peak_idx, peak_price, pullback_tolerance)
    if local_min_result:
        candidates.append(local_min_result)
    
    # Strateji 2: Momentum Turning Point (RSI/MACD dönüş)
    if 'rsi_15m' in search_window.columns:
        momentum_result = _find_momentum_turn(search_window, peak_idx, peak_price)
        if momentum_result:
            candidates.append(momentum_result)
    
    # Strateji 3: Volume Surge (Hacim patlaması öncesi)
    if 'volume' in search_window.columns:
        volume_result = _find_volume_surge_start(search_window, peak_idx, peak_price)
        if volume_result:
            candidates.append(volume_result)
    
    # En iyi candidate'i seç (en yüksek confidence)
    if candidates:
        best = max(candidates, key=lambda x: x['confidence'])
        return best
    else:
        # Fallback: En düşük close fiyatı
        logger.warning(f"Rally start bulunamadı, fallback: en düşük fiyat")
        return _find_simple_minimum(search_window, peak_idx, peak_price)


def _find_local_minimum(
    window: pd.DataFrame,
    peak_idx: int,
    peak_price: float,
    tolerance: float
) -> Optional[Dict]:
    """
    Local minimum bul (pullback tolerance ile).
    
    Sliding window ile en düşük noktayı bul, ama tolerance dahilinde
    başka minimumlar varsa en erken olanı tercih et.
    """
    
    closes = window['close'].values
    
    # En düşük fiyat
    min_price = closes.min()
    min_idx_in_window = closes.argmin()
    
    # Tolerance dahilindeki diğer düşük noktalar
    threshold = min_price * (1 + tolerance)
    candidates_in_tolerance = np.where(closes <= threshold)[0]
    
    # En erken olanı al (rally en erken başlayan)
    earliest_idx_in_window = candidates_in_tolerance[0] if len(candidates_in_tolerance) > 0 else min_idx_in_window
    
    rally_start_idx = window.index[earliest_idx_in_window]
    rally_start_price = closes[earliest_idx_in_window]
    
    # Gain hesapla
    true_gain_pct = (peak_price - rally_start_price) / rally_start_price
    
    # Confidence: Eğer minimum çok net ise (etrafı daha yüksek) confidence yüksek
    # Basit heuristic: Öncesi ve sonrası %2+ yüksekse net minimum
    confidence = 0.7  # Base
    if earliest_idx_in_window > 0 and earliest_idx_in_window < len(closes) - 1:
        prev_price = closes[earliest_idx_in_window - 1]
        next_price = closes[earliest_idx_in_window + 1]
        if prev_price > rally_start_price * 1.01 and next_price > rally_start_price * 1.01:
            confidence = 0.9  # Net V-shape
    
    return {
        'rally_start_idx': rally_start_idx,
        'rally_start_price': rally_start_price,
        'rally_start_time': window.loc[rally_start_idx, 'timestamp'] if 'timestamp' in window.columns else rally_start_idx,
        'true_gain_pct': true_gain_pct,
        'bars_duration': peak_idx - rally_start_idx,
        'confidence': confidence,
        'method': 'local_minimum'
    }


def _find_momentum_turn(
    window: pd.DataFrame,
    peak_idx: int,
    peak_price: float
) -> Optional[Dict]:
    """
    RSI veya MACD dönüş noktasını bul.
    
    RSI oversold'dan çıkış veya MACD pozitife dönüş.
    """
    
    if 'rsi_15m' not in window.columns:
        return None
    
    rsi = window['rsi_15m'].values
    closes = window['close'].values
    
    # RSI 30'un altından yukarı çıkan ilk bar
    oversold_threshold = 30
    oversold_exit_idx = None
    
    for i in range(len(rsi) - 1):
        if rsi[i] < oversold_threshold and rsi[i + 1] >= oversold_threshold:
            oversold_exit_idx = i + 1
            break
    
    if oversold_exit_idx is None:
        # RSI dönüş yok, en düşük RSI noktası
        oversold_exit_idx = rsi.argmin()
    
    rally_start_idx = window.index[oversold_exit_idx]
    rally_start_price = closes[oversold_exit_idx]
    true_gain_pct = (peak_price - rally_start_price) / rally_start_price
    
    return {
        'rally_start_idx': rally_start_idx,
        'rally_start_price': rally_start_price,
        'rally_start_time': window.loc[rally_start_idx, 'timestamp'] if 'timestamp' in window.columns else rally_start_idx,
        'true_gain_pct': true_gain_pct,
        'bars_duration': peak_idx - rally_start_idx,
        'confidence': 0.75,
        'method': 'momentum_turn'
    }


def _find_volume_surge_start(
    window: pd.DataFrame,
    peak_idx: int,
    peak_price: float
) -> Optional[Dict]:
    """
    Hacim patlaması öncesindeki düşük hacim noktasını bul.
    
    Accumulation sonrası distribution başlangıcı.
    """
    
    if 'volume' not in window.columns:
        return None
    
    volumes = window['volume'].values
    closes = window['close'].values
    
    # Volume moving average (5 bar)
    vol_ma = pd.Series(volumes).rolling(5, min_periods=1).mean().values
    
    # Hacim spike: MA'nın 2x üstü
    spikes = volumes > vol_ma * 2
    
    if not spikes.any():
        return None
    
    # İlk spike öncesi
    first_spike_idx = np.where(spikes)[0][0]
    
    if first_spike_idx == 0:
        return None
    
    # Spike öncesi düşük hacim bölgesi
    rally_start_idx_in_window = max(0, first_spike_idx - 3)  # 3 bar önce
    
    rally_start_idx = window.index[rally_start_idx_in_window]
    rally_start_price = closes[rally_start_idx_in_window]
    true_gain_pct = (peak_price - rally_start_price) / rally_start_price
    
    return {
        'rally_start_idx': rally_start_idx,
        'rally_start_price': rally_start_price,
        'rally_start_time': window.loc[rally_start_idx, 'timestamp'] if 'timestamp' in window.columns else rally_start_idx,
        'true_gain_pct': true_gain_pct,
        'bars_duration': peak_idx - rally_start_idx,
        'confidence': 0.65,
        'method': 'volume_surge'
    }


def _find_simple_minimum(window: pd.DataFrame, peak_idx: int, peak_price: float) -> Dict:
    """
    Basit fallback: En düşük close fiyatı.
    """
    closes = window['close'].values
    min_idx_in_window = closes.argmin()
    
    rally_start_idx = window.index[min_idx_in_window]
    rally_start_price = closes[min_idx_in_window]
    true_gain_pct = (peak_price - rally_start_price) / rally_start_price
    
    return {
        'rally_start_idx': rally_start_idx,
        'rally_start_price': rally_start_price,
        'rally_start_time': window.loc[rally_start_idx, 'timestamp'] if 'timestamp' in window.columns else rally_start_idx,
        'true_gain_pct': true_gain_pct,
        'bars_duration': peak_idx - rally_start_idx,
        'confidence': 0.5,
        'method': 'simple_minimum'
    }


def _create_fallback_result(df: pd.DataFrame, peak_idx: int, peak_price: float) -> Dict:
    """
    Yetersiz veri durumunda fallback result.
    """
    return {
        'rally_start_idx': peak_idx,
        'rally_start_price': peak_price,
        'rally_start_time': df.loc[peak_idx, 'timestamp'] if 'timestamp' in df.columns else peak_idx,
        'true_gain_pct': 0.0,
        'bars_duration': 0,
        'confidence': 0.0,
        'method': 'fallback'
    }
