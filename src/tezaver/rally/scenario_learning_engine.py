"""
Tezaver Scenario Learning Engine
================================

Rally verilerinden coin-spesifik senaryo profillerini ÖĞRENEN modül.

Yaklaşım:
1. Mevcut rally'leri yükle (fast15, time_labs)
2. Her rally anındaki metrikleri topla
3. Metriklere göre senaryoları TANIMLA (veriden öğren)
4. Coin-spesifik senaryo profilleri oluştur

Senaryo Metaforları:
- Yorgun Savaşçı 🥵: Uzun yükselişin son nefesi
- Rüzgarı Arkana Al 🌬️: Tüm trendler aynı yönde
- Fırtınada Sörf 🏄‍♂️: Ana trend düşüşte, kısa fırsat
- Güç Patlaması 💥: Ani güçlü hareket
- Belirsiz Sular 🌊: Karışık sinyaller
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import json

from tezaver.core import coin_cell_paths
from tezaver.core.logging_utils import get_logger
from tezaver.core.config import DEFAULT_COINS

logger = get_logger(__name__)


# =============================================================================
# SENARYO TANIMLARI
# =============================================================================

SCENARIO_METAPHORS = {
    "EXHAUSTION": {
        "name_tr": "Yorgun Savaşçı 🥵",
        "meaning": "Uzun yükselişin son nefesi, düşüş kapıda",
        "expected_signs": ["RSI yüksek", "MACD zayıflıyor", "Hacim düşüyor"],
    },
    "BREAKOUT": {
        "name_tr": "Rüzgarı Arkana Al 🌬️", 
        "meaning": "Tüm trendler aynı yönde, risk düşük",
        "expected_signs": ["EMA'lar hizalı", "MACD güçlü", "Trend yukarı"],
    },
    "SURF": {
        "name_tr": "Fırtınada Sörf 🏄‍♂️",
        "meaning": "Ana trend düşüşte, kısa fırsat, riskli",
        "expected_signs": ["EMA'lar aşağı", "RSI düşük", "MACD toparlanıyor"],
    },
    "POWER_PUMP": {
        "name_tr": "Güç Patlaması 💥",
        "meaning": "Ani güçlü hareket, momentum patlaması",
        "expected_signs": ["RSI patlıyor", "Hacim patlıyor", "Hızlı hareket"],
    },
    "NEUTRAL": {
        "name_tr": "Belirsiz Sular 🌊",
        "meaning": "Karışık sinyaller, bekle gör",
        "expected_signs": ["Karışık indikatörler", "Net yön yok"],
    },
}


@dataclass
class ScenarioProfile:
    """Bir senaryo için öğrenilmiş sayısal profil."""
    scenario_id: str
    symbol: str
    timeframe: str
    
    # RSI profili
    rsi_min: float
    rsi_max: float
    rsi_avg: float
    rsi_ema_diff_avg: float
    
    # MACD profili
    macd_color_dist: Dict[str, float]  # {"green": 0.4, "lime": 0.3, ...}
    macd_cross_dist: Dict[str, float]  # {"bullish_cross": 0.2, ...}
    
    # EMA profili
    ema_alignment_dist: Dict[str, float]  # {"bullish": 0.6, ...}
    
    # Volume profili
    vol_rel_avg: float
    vol_spike_pct: float  # % of rallies with vol_spike
    
    # Örnek sayısı
    sample_count: int
    
    # Rally sonuçları
    avg_gain_pct: float
    avg_duration_bars: float


def load_rally_events(symbol: str, timeframe: str) -> pd.DataFrame:
    """Rally olaylarını yükle."""
    if timeframe == "15m":
        rally_file = coin_cell_paths.get_fast15_rallies_path(symbol)
    else:
        # time_labs için
        rally_dir = coin_cell_paths.get_coin_profile_dir(symbol)
        rally_file = rally_dir / f"time_labs_{timeframe}.parquet"
    
    if not rally_file.exists():
        logger.warning(f"Rally file not found: {rally_file}")
        return pd.DataFrame()
    
    return pd.read_parquet(rally_file)


def load_features(symbol: str, timeframe: str) -> pd.DataFrame:
    """Feature dosyasını yükle."""
    data_dir = coin_cell_paths.get_coin_data_dir(symbol)
    feature_file = data_dir / f"features_{timeframe}.parquet"
    
    if not feature_file.exists():
        logger.warning(f"Feature file not found: {feature_file}")
        return pd.DataFrame()
    
    return pd.read_parquet(feature_file)


def classify_rally_scenario(metrics: Dict) -> str:
    """
    Bir rally'nin metriklerine bakarak hangi senaryoya ait olduğunu BELİRLE.
    
    Bu fonksiyon VERİDEN öğrenilen kurallara göre çalışacak.
    Şimdilik basit kurallar, sonra coin-spesifik hale getirilecek.
    """
    rsi = metrics.get('rsi', 50)
    rsi_ema_diff = metrics.get('rsi_ema_diff', 0)
    ema_alignment = metrics.get('ema_alignment', 'mixed')
    macd_color = metrics.get('macd_hist_color', 'gray')
    vol_spike = metrics.get('vol_spike', 0)
    
    # Yorgun Savaşçı: RSI çok yüksek, momentum zayıflıyor
    if rsi > 70 and macd_color in ['lime', 'orange']:
        return "EXHAUSTION"
    
    # Rüzgarı Arkana Al: Her şey hizalı
    if ema_alignment == 'bullish' and macd_color == 'green':
        return "BREAKOUT"
    
    # Fırtınada Sörf: Trend düşük ama toparlanma sinyalleri
    if ema_alignment == 'bearish' and rsi < 40 and macd_color == 'orange':
        return "SURF"
    
    # Güç Patlaması: RSI ve hacim patlıyor
    if rsi > 65 and rsi_ema_diff > 5 and vol_spike == 1:
        return "POWER_PUMP"
    
    # Belirsiz
    return "NEUTRAL"


def analyze_rally_scenarios(
    symbol: str,
    timeframe: str
) -> Dict[str, ScenarioProfile]:
    """
    Bir coin için tüm rally'leri analiz et ve senaryo profilleri çıkar.
    """
    # Rally ve feature verilerini yükle
    rallies_df = load_rally_events(symbol, timeframe)
    features_df = load_features(symbol, timeframe)
    
    if rallies_df.empty or features_df.empty:
        logger.warning(f"No data for {symbol} {timeframe}")
        return {}
    
    # Her rally için metrik profili çıkar
    rally_profiles = []
    
    for _, rally in rallies_df.iterrows():
        # Rally zamanını bul
        event_time = rally.get('event_time', rally.get('timestamp'))
        if event_time is None:
            continue
        
        # Metrikleri al (rally içinde olabilir veya features'tan çekmemiz gerekebilir)
        metrics = {
            'rsi': rally.get('rsi') or rally.get('rsi_15m', 50),
            'rsi_ema_diff': rally.get('rsi_ema_diff', 0),
            'ema_alignment': rally.get('ema_alignment', 'mixed'),
            'macd_hist_color': rally.get('macd_hist_color', 'gray'),
            'macd_cross': rally.get('macd_cross', 'none'),
            'vol_spike': rally.get('vol_spike', 0),
            'vol_rel': rally.get('vol_rel') or rally.get('volume_rel_15m', 1),
            'future_max_gain_pct': rally.get('future_max_gain_pct', 0),
            'bars_to_peak': rally.get('bars_to_peak', 0),
        }
        
        # Senaryoyu belirle
        scenario = classify_rally_scenario(metrics)
        metrics['scenario'] = scenario
        
        rally_profiles.append(metrics)
    
    if not rally_profiles:
        return {}
    
    profiles_df = pd.DataFrame(rally_profiles)
    
    # Her senaryo için istatistik çıkar
    scenario_profiles = {}
    
    for scenario_id in profiles_df['scenario'].unique():
        scenario_data = profiles_df[profiles_df['scenario'] == scenario_id]
        
        if len(scenario_data) < 3:  # En az 3 örnek
            continue
        
        # MACD renk dağılımı
        macd_colors = scenario_data['macd_hist_color'].value_counts(normalize=True).to_dict()
        macd_crosses = scenario_data['macd_cross'].value_counts(normalize=True).to_dict()
        ema_aligns = scenario_data['ema_alignment'].value_counts(normalize=True).to_dict()
        
        profile = ScenarioProfile(
            scenario_id=scenario_id,
            symbol=symbol,
            timeframe=timeframe,
            rsi_min=scenario_data['rsi'].min(),
            rsi_max=scenario_data['rsi'].max(),
            rsi_avg=scenario_data['rsi'].mean(),
            rsi_ema_diff_avg=scenario_data['rsi_ema_diff'].mean(),
            macd_color_dist=macd_colors,
            macd_cross_dist=macd_crosses,
            ema_alignment_dist=ema_aligns,
            vol_rel_avg=scenario_data['vol_rel'].mean(),
            vol_spike_pct=scenario_data['vol_spike'].mean() * 100,
            sample_count=len(scenario_data),
            avg_gain_pct=scenario_data['future_max_gain_pct'].mean() * 100,
            avg_duration_bars=scenario_data['bars_to_peak'].mean(),
        )
        
        scenario_profiles[scenario_id] = profile
    
    return scenario_profiles


def generate_scenario_report(symbol: str, timeframe: str) -> pd.DataFrame:
    """Senaryo raporu oluştur."""
    profiles = analyze_rally_scenarios(symbol, timeframe)
    
    if not profiles:
        return pd.DataFrame()
    
    rows = []
    for scenario_id, profile in profiles.items():
        meta = SCENARIO_METAPHORS.get(scenario_id, {})
        rows.append({
            'Senaryo': meta.get('name_tr', scenario_id),
            'Örnek': profile.sample_count,
            'RSI Ort.': f"{profile.rsi_avg:.0f}",
            'RSI Aralık': f"{profile.rsi_min:.0f}-{profile.rsi_max:.0f}",
            'RSI-EMA': f"{profile.rsi_ema_diff_avg:+.1f}",
            'Hacim Rel': f"{profile.vol_rel_avg:.1f}x",
            'Vol Spike%': f"{profile.vol_spike_pct:.0f}%",
            'Ort.Kazanç%': f"{profile.avg_gain_pct:.1f}%",
            'Ort.Süre': f"{profile.avg_duration_bars:.0f} bar",
        })
    
    return pd.DataFrame(rows).sort_values('Örnek', ascending=False)


def save_scenario_profiles(symbol: str, profiles: Dict[str, ScenarioProfile]):
    """Senaryo profillerini JSON olarak kaydet."""
    profile_dir = coin_cell_paths.get_coin_profile_dir(symbol)
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = profile_dir / "scenario_profiles.json"
    
    # Convert dataclass to dict
    data = {
        "symbol": symbol,
        "profiles": {k: asdict(v) for k, v in profiles.items()}
    }
    
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    
    logger.info(f"Saved scenario profiles to {output_file}")
