"""
Tezaver Pattern Discovery Engine
================================

Verideki kalıpları keşfeder ve her kalıbın sonuçlarını analiz eder.
Coin-spesifik senaryo profilleri oluşturmak için temel altyapı.

Felsefe:
- Kalıplar statik değil, veriden öğrenilir
- Her coin farklı tepki verir, bu yüzden coin-spesifik analiz yapılır
- Sonuçlar zaman dilimine göre ayrı ayrı incelenir
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime

from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger
from tezaver.core.config import DEFAULT_COINS

logger = get_logger(__name__)


# =============================================================================
# KALIP TANIMLARI (Pattern Definitions)
# =============================================================================

@dataclass
class PatternMatch:
    """Tek bir kalıp eşleşmesi."""
    pattern_id: str
    bar_index: int
    timestamp: datetime
    metrics_snapshot: Dict  # O andaki metrik değerleri


@dataclass
class PatternOutcome:
    """Kalıp sonrası ne olduğu."""
    bars_forward: int
    max_gain_pct: float
    max_loss_pct: float
    final_pct: float
    hit_5p: bool
    hit_10p: bool


@dataclass
class PatternStats:
    """Bir kalıbın istatistikleri."""
    pattern_id: str
    match_count: int
    avg_gain_pct: float
    avg_loss_pct: float
    win_rate_5p: float
    win_rate_10p: float
    avg_bars_to_peak: float
    outcomes: List[PatternOutcome] = field(default_factory=list)


# =============================================================================
# KALIP KOŞUL FONKSİYONLARI
# =============================================================================

def condition_exhaustion(row: pd.Series) -> bool:
    """
    EXHAUSTION (Yorgun Savaşçı):
    - Günlük RSI > 70 (aşırı alım)
    - MACD histogram azalıyor (lime veya orange)
    """
    rsi_1d = row.get('rsi_1d', row.get('rsi', 50))
    macd_color = row.get('macd_hist_color_1d', row.get('macd_hist_color', 'gray'))
    
    return rsi_1d > 70 and macd_color in ['lime', 'orange']


def condition_breakout(row: pd.Series) -> bool:
    """
    BREAKOUT (Trend Kırılımı):
    - EMA alignment bullish
    - MACD bullish cross veya histogram green
    - Volume spike
    """
    ema_align = row.get('ema_alignment', 'mixed')
    macd_cross = row.get('macd_cross', 'none')
    macd_color = row.get('macd_hist_color', 'gray')
    vol_spike = row.get('vol_spike', 0)
    
    ema_ok = ema_align == 'bullish'
    macd_ok = macd_cross == 'bullish_cross' or macd_color == 'green'
    vol_ok = vol_spike == 1
    
    return ema_ok and macd_ok and vol_ok


def condition_surf(row: pd.Series) -> bool:
    """
    SURF (Fırtınada Sörf):
    - EMA alignment bearish (düşüş trendi)
    - RSI < 35 (aşırı satım)
    - MACD histogram orange (ayı zayıflıyor)
    """
    ema_align = row.get('ema_alignment', 'mixed')
    rsi = row.get('rsi', 50)
    macd_color = row.get('macd_hist_color', 'gray')
    
    return ema_align == 'bearish' and rsi < 35 and macd_color == 'orange'


def condition_power_pump(row: pd.Series) -> bool:
    """
    POWER_PUMP (Güç Patlaması):
    - RSI > 70 (güçlü momentum)
    - RSI > RSI_EMA (rsi_ema_diff > 0)
    - Volume spike
    """
    rsi = row.get('rsi', 50)
    rsi_ema_diff = row.get('rsi_ema_diff', 0)
    vol_spike = row.get('vol_spike', 0)
    
    return rsi > 70 and rsi_ema_diff > 5 and vol_spike == 1


def condition_macd_bullish_cross(row: pd.Series) -> bool:
    """
    MACD_BULLISH_CROSS:
    - MACD çizgisi signal'ı yukarı kesti
    """
    macd_cross = row.get('macd_cross', 'none')
    return macd_cross == 'bullish_cross'


def condition_rsi_divergence_bullish(row: pd.Series) -> bool:
    """
    RSI_DIVERGENCE_BULLISH:
    - RSI < 40 ama yükseliyor (rsi_ema_diff pozitif ve artıyor)
    - Fiyat düşerken RSI yükseliyor sinyali
    """
    rsi = row.get('rsi', 50)
    rsi_ema_diff = row.get('rsi_ema_diff', 0)
    
    # Basit divergence: RSI düşük ama momentum pozitif
    return rsi < 40 and rsi_ema_diff > 3


def condition_volume_spike(row: pd.Series) -> bool:
    """
    VOLUME_SPIKE:
    - Hacim normalin 2x+ üzerinde
    """
    vol_spike = row.get('vol_spike', 0)
    return vol_spike == 1


# Kalıp registry
PATTERN_CONDITIONS: Dict[str, Callable[[pd.Series], bool]] = {
    "EXHAUSTION": condition_exhaustion,
    "BREAKOUT": condition_breakout,
    "SURF": condition_surf,
    "POWER_PUMP": condition_power_pump,
    "MACD_BULLISH_CROSS": condition_macd_bullish_cross,
    "RSI_DIVERGENCE_BULLISH": condition_rsi_divergence_bullish,
    "VOLUME_SPIKE": condition_volume_spike,
}

PATTERN_LABELS_TR = {
    "EXHAUSTION": "Yorgun Savaşçı 🥵",
    "BREAKOUT": "Trend Kırılımı 🚀",
    "SURF": "Fırtınada Sörf 🏄‍♂️",
    "POWER_PUMP": "Güç Patlaması 💥",
    "MACD_BULLISH_CROSS": "MACD Boğa Kesişimi 📈",
    "RSI_DIVERGENCE_BULLISH": "RSI Pozitif Uyumsuzluk 🔄",
    "VOLUME_SPIKE": "Hacim Patlaması 📊",
}


# =============================================================================
# KALIP TARAMA FONKSİYONLARI
# =============================================================================

def find_pattern_matches(
    df: pd.DataFrame,
    pattern_id: str,
    condition_fn: Callable[[pd.Series], bool]
) -> List[PatternMatch]:
    """
    DataFrame'de kalıp eşleşmelerini bulur.
    """
    matches = []
    
    for idx in range(len(df)):
        row = df.iloc[idx]
        
        try:
            if condition_fn(row):
                timestamp = row.get('timestamp', row.get('open_time', None))
                if timestamp is None and df.index.name == 'timestamp':
                    timestamp = df.index[idx]
                
                match = PatternMatch(
                    pattern_id=pattern_id,
                    bar_index=idx,
                    timestamp=timestamp,
                    metrics_snapshot={
                        'rsi': row.get('rsi'),
                        'rsi_ema_diff': row.get('rsi_ema_diff'),
                        'macd_hist_color': row.get('macd_hist_color'),
                        'macd_cross': row.get('macd_cross'),
                        'ema_alignment': row.get('ema_alignment'),
                        'vol_spike': row.get('vol_spike'),
                        'vol_rel': row.get('vol_rel'),
                    }
                )
                matches.append(match)
        except Exception as e:
            continue
    
    return matches


def analyze_pattern_outcome(
    df: pd.DataFrame,
    match: PatternMatch,
    lookahead_bars: int = 20
) -> Optional[PatternOutcome]:
    """
    Kalıp eşleşmesinden sonra ne olduğunu analiz eder.
    """
    start_idx = match.bar_index
    end_idx = min(start_idx + lookahead_bars, len(df) - 1)
    
    if end_idx <= start_idx:
        return None
    
    entry_price = df.iloc[start_idx]['close']
    future_slice = df.iloc[start_idx+1:end_idx+1]
    
    if future_slice.empty:
        return None
    
    # Maksimum kazanç/kayıp hesapla
    max_high = future_slice['high'].max()
    min_low = future_slice['low'].min()
    final_close = future_slice.iloc[-1]['close']
    
    max_gain_pct = (max_high / entry_price - 1) * 100
    max_loss_pct = (min_low / entry_price - 1) * 100
    final_pct = (final_close / entry_price - 1) * 100
    
    # Bars to peak
    peak_idx = future_slice['high'].idxmax()
    if hasattr(peak_idx, '__iter__'):
        bars_to_peak = future_slice.index.get_loc(peak_idx)
    else:
        bars_to_peak = future_slice.index.get_loc(peak_idx) if peak_idx in future_slice.index else 0
    
    return PatternOutcome(
        bars_forward=len(future_slice),
        max_gain_pct=max_gain_pct,
        max_loss_pct=max_loss_pct,
        final_pct=final_pct,
        hit_5p=max_gain_pct >= 5,
        hit_10p=max_gain_pct >= 10
    )


def scan_pattern_for_symbol(
    symbol: str,
    timeframe: str,
    pattern_id: str,
    lookahead_bars: int = 20
) -> PatternStats:
    """
    Bir coin ve zaman dilimi için kalıp taraması yapar.
    """
    # Feature dosyasını yükle
    data_dir = coin_cell_paths.get_coin_data_dir(symbol)
    feature_file = data_dir / f"features_{timeframe}.parquet"
    
    if not feature_file.exists():
        logger.warning(f"Feature file not found: {feature_file}")
        return PatternStats(
            pattern_id=pattern_id,
            match_count=0,
            avg_gain_pct=0,
            avg_loss_pct=0,
            win_rate_5p=0,
            win_rate_10p=0,
            avg_bars_to_peak=0
        )
    
    df = pd.read_parquet(feature_file)
    
    # Kalıp koşul fonksiyonunu al
    condition_fn = PATTERN_CONDITIONS.get(pattern_id)
    if not condition_fn:
        raise ValueError(f"Unknown pattern: {pattern_id}")
    
    # Eşleşmeleri bul
    matches = find_pattern_matches(df, pattern_id, condition_fn)
    
    if not matches:
        return PatternStats(
            pattern_id=pattern_id,
            match_count=0,
            avg_gain_pct=0,
            avg_loss_pct=0,
            win_rate_5p=0,
            win_rate_10p=0,
            avg_bars_to_peak=0
        )
    
    # Sonuçları analiz et
    outcomes = []
    for match in matches:
        outcome = analyze_pattern_outcome(df, match, lookahead_bars)
        if outcome:
            outcomes.append(outcome)
    
    if not outcomes:
        return PatternStats(
            pattern_id=pattern_id,
            match_count=len(matches),
            avg_gain_pct=0,
            avg_loss_pct=0,
            win_rate_5p=0,
            win_rate_10p=0,
            avg_bars_to_peak=0,
            outcomes=[]
        )
    
    # İstatistikleri hesapla
    gains = [o.max_gain_pct for o in outcomes]
    losses = [o.max_loss_pct for o in outcomes]
    
    return PatternStats(
        pattern_id=pattern_id,
        match_count=len(matches),
        avg_gain_pct=np.mean(gains),
        avg_loss_pct=np.mean(losses),
        win_rate_5p=sum(1 for o in outcomes if o.hit_5p) / len(outcomes) * 100,
        win_rate_10p=sum(1 for o in outcomes if o.hit_10p) / len(outcomes) * 100,
        avg_bars_to_peak=np.mean([o.bars_forward for o in outcomes]),
        outcomes=outcomes
    )


def scan_all_patterns_for_symbol(
    symbol: str,
    timeframe: str,
    lookahead_bars: int = 20
) -> Dict[str, PatternStats]:
    """
    Bir coin için tüm kalıpları tarar.
    """
    results = {}
    
    for pattern_id in PATTERN_CONDITIONS.keys():
        logger.info(f"Scanning {pattern_id} for {symbol} {timeframe}...")
        stats = scan_pattern_for_symbol(symbol, timeframe, pattern_id, lookahead_bars)
        results[pattern_id] = stats
    
    return results


def generate_pattern_report(
    symbol: str,
    timeframe: str,
    lookahead_bars: int = 20
) -> pd.DataFrame:
    """
    Bir coin için kalıp raporu oluşturur.
    """
    results = scan_all_patterns_for_symbol(symbol, timeframe, lookahead_bars)
    
    rows = []
    for pattern_id, stats in results.items():
        rows.append({
            'Kalıp': PATTERN_LABELS_TR.get(pattern_id, pattern_id),
            'Eşleşme': stats.match_count,
            'Ort.Kazanç%': f"{stats.avg_gain_pct:.1f}%",
            'Ort.Kayıp%': f"{stats.avg_loss_pct:.1f}%",
            '%5+ Win': f"{stats.win_rate_5p:.0f}%",
            '%10+ Win': f"{stats.win_rate_10p:.0f}%",
        })
    
    return pd.DataFrame(rows).sort_values('Eşleşme', ascending=False)
