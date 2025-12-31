"""
Precision Rally Miner
=====================
Hassas Madencilik: Tüm rallyleri yakala, optimal giriş/çıkış hesapla.

Kurallar:
- Giriş: Patlama barından 1-2 bar ÖNCE
- Çıkış: Tepeden 1 bar SONRA
- Çoklu pencere ile tarama (5, 15, 30 bar)
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from tezaver.core.logging_utils import get_logger
from tezaver.core import coin_cell_paths
from tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct

logger = get_logger(__name__)


@dataclass
class PrecisionRally:
    """Hassas rally verisi."""
    symbol: str
    timeframe: str
    
    # Ham tespit (eski sistem uyumu)
    raw_dip_idx: int
    raw_peak_idx: int
    raw_gain_pct: float  # Ham dip-peak kazancı (tier için kullanılır)
    
    # Rafine edilmiş giriş
    entry_idx: int
    entry_time: pd.Timestamp
    entry_price: float
    
    # Rafine edilmiş çıkış
    exit_idx: int
    exit_time: pd.Timestamp
    exit_price: float
    
    # Patlama bilgisi
    breakout_idx: int
    breakout_time: pd.Timestamp
    
    # Metrikler
    gain_pct: float  # Rafine entry/exit kazancı
    bars_to_peak: int
    tier: Optional[str]  # raw_gain_pct'ye göre hesaplanır
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'timeframe': self.timeframe,
            'raw_dip_idx': self.raw_dip_idx,
            'raw_peak_idx': self.raw_peak_idx,
            'raw_gain_pct': self.raw_gain_pct,
            'entry_idx': self.entry_idx,
            'entry_time': self.entry_time,
            'entry_price': self.entry_price,
            'exit_idx': self.exit_idx,
            'exit_time': self.exit_time,
            'exit_price': self.exit_price,
            'breakout_idx': self.breakout_idx,
            'breakout_time': self.breakout_time,
            'gain_pct': self.gain_pct,
            'bars_to_peak': self.bars_to_peak,
            'tier': self.tier,
        }


def multi_pass_detection(
    df: pd.DataFrame,
    window_sizes: List[int] = [5, 15, 30],
    min_gain: float = 0.05,
    max_lookahead: int = 100
) -> List[Tuple[int, int, float]]:
    """
    Çoklu pencere boyutuyla rally tespiti.
    
    Returns:
        List of (dip_idx, peak_idx, gain_pct) tuples
    """
    all_rallies = []
    
    for window_radius in window_sizes:
        window_size = (window_radius * 2) + 1
        
        # Rolling extrema
        df['rolling_min'] = df['low'].rolling(window=window_size, center=True).min()
        df['is_dip'] = (df['low'] == df['rolling_min']) & df['rolling_min'].notna()
        
        df['rolling_max'] = df['high'].rolling(window=window_size, center=True).max()
        df['is_peak'] = (df['high'] == df['rolling_max']) & df['rolling_max'].notna()
        
        dip_indices = df.index[df['is_dip']].tolist()
        peak_indices = df.index[df['is_peak']].tolist()
        
        for dip_idx in dip_indices:
            future_peaks = [p for p in peak_indices if dip_idx < p <= dip_idx + max_lookahead]
            
            if not future_peaks:
                continue
            
            dip_price = df.at[dip_idx, 'low']
            if dip_price <= 0:
                continue
            
            best_peak_idx = None
            best_gain = 0
            
            for peak_idx in future_peaks:
                peak_price = df.at[peak_idx, 'high']
                gain_pct = (peak_price - dip_price) / dip_price
                
                if gain_pct > best_gain:
                    best_gain = gain_pct
                    best_peak_idx = peak_idx
            
            if best_gain >= min_gain and best_peak_idx is not None:
                all_rallies.append((dip_idx, best_peak_idx, best_gain))
    
    # Tekrarları temizle (aynı peak'e düşenlerden en iyisini al)
    if not all_rallies:
        return []
    
    df_rallies = pd.DataFrame(all_rallies, columns=['dip_idx', 'peak_idx', 'gain_pct'])
    df_dedup = df_rallies.sort_values('gain_pct', ascending=False).groupby('peak_idx').first().reset_index()
    
    # Semantic lockout (çakışan rallileri temizle)
    # FARK: Önce KAZANCA göre sırala (Diamond önceliği için)
    # Böylece çakışan rallilerde en yüksek kazançlı olan kalır
    df_dedup = df_dedup.sort_values('gain_pct', ascending=False)
    
    final_rallies = []
    covered_ranges = []  # (start, end) aralıkları
    
    for _, row in df_dedup.iterrows():
        dip_idx = int(row['dip_idx'])
        peak_idx = int(row['peak_idx'])
        
        # Bu rally mevcut aralıklarla çakışıyor mu?
        is_overlapping = False
        for start, end in covered_ranges:
            if not (dip_idx > end or peak_idx < start):
                is_overlapping = True
                break
        
        if not is_overlapping:
            final_rallies.append((dip_idx, peak_idx, row['gain_pct']))
            covered_ranges.append((dip_idx, peak_idx))
    
    # Dip index'e göre sırala (kronolojik)
    final_rallies.sort(key=lambda x: x[0])
    
    return final_rallies


def find_breakout_bar(
    df: pd.DataFrame,
    dip_idx: int,
    peak_idx: int,
    bar_gain_threshold: float = 0.015,  # %1.5 tek bar hareket
    volume_multiplier: float = 1.5
) -> int:
    """
    Patlama barını bul: Fiyatın hızlı yükselmeye başladığı ilk bar.
    
    Kriterler (en az biri):
    1. Tek bar kazancı > threshold
    2. Hacim > ortalamanın X katı
    """
    if dip_idx >= peak_idx:
        return dip_idx
    
    # Hacim ortalaması
    vol_mean = df['volume'].rolling(20).mean()
    
    for i in range(dip_idx, min(peak_idx, dip_idx + 50)):
        if i == 0:
            continue
            
        # Bar kazancı
        prev_close = df.at[i-1, 'close'] if i > 0 else df.at[i, 'open']
        curr_close = df.at[i, 'close']
        bar_gain = (curr_close - prev_close) / prev_close if prev_close > 0 else 0
        
        # Patlama kriteri 1: Büyük tek bar hareket
        if bar_gain > bar_gain_threshold:
            return i
        
        # Patlama kriteri 2: Hacim patlaması
        if pd.notna(vol_mean.at[i]) and vol_mean.at[i] > 0:
            if df.at[i, 'volume'] > vol_mean.at[i] * volume_multiplier:
                return i
    
    # Fallback: dip + 1
    return dip_idx + 1


def find_impulse_zone(
    df: pd.DataFrame,
    dip_idx: int,
    peak_idx: int,
    window_size: int = 10  # Kaç bar'lık pencere aranacak
) -> Tuple[int, int, float]:
    """
    Yoğun Bölge (Impulse Zone) Tespiti:
    Rally içindeki en yoğun hareketin olduğu pencereyi bul.
    
    Args:
        df: DataFrame
        dip_idx: Dip index
        peak_idx: Peak index
        window_size: Pencere boyutu (default 10 bar)
    
    Returns:
        (impulse_start_idx, impulse_end_idx, impulse_gain_pct)
    """
    if peak_idx - dip_idx <= window_size:
        # Rally zaten kısa, tamamını döndür
        dip_price = df.at[dip_idx, 'low']
        peak_price = df.at[peak_idx, 'high']
        gain = (peak_price - dip_price) / dip_price if dip_price > 0 else 0
        return dip_idx, peak_idx, gain
    
    best_start = dip_idx
    best_gain = 0
    
    # Her pencere için kazanç hesapla
    for i in range(dip_idx, peak_idx - window_size + 1):
        window_low = df.loc[i:i+window_size, 'low'].min()
        window_high = df.loc[i:i+window_size, 'high'].max()
        window_gain = (window_high - window_low) / window_low if window_low > 0 else 0
        
        if window_gain > best_gain:
            best_gain = window_gain
            best_start = i
    
    best_end = min(best_start + window_size, peak_idx)
    
    return best_start, best_end, best_gain


def calculate_entry_point(
    df: pd.DataFrame,
    breakout_idx: int,
    offset: int = 1  # Patlamadan kaç bar önce
) -> Tuple[int, pd.Timestamp, float]:
    """
    Giriş noktası hesapla: Patlama barından 1 bar önce.
    """
    entry_idx = max(0, breakout_idx - offset)
    entry_time = df.at[entry_idx, 'timestamp'] if 'timestamp' in df.columns else df.index[entry_idx]
    entry_price = df.at[entry_idx, 'close']
    
    return entry_idx, entry_time, entry_price


def calculate_exit_point(
    df: pd.DataFrame,
    peak_idx: int,
    offset: int = 1  # Tepeden kaç bar sonra
) -> Tuple[int, pd.Timestamp, float]:
    """
    Çıkış noktası hesapla: Tepeden 1 bar sonra.
    """
    exit_idx = min(len(df) - 1, peak_idx + offset)
    exit_time = df.at[exit_idx, 'timestamp'] if 'timestamp' in df.columns else df.index[exit_idx]
    exit_price = df.at[exit_idx, 'close']
    
    return exit_idx, exit_time, exit_price


def mine_precision_rallies(
    symbol: str,
    timeframe: str,
    min_tier: str = "BRONZE"  # Minimum tier filtresi
) -> List[PrecisionRally]:
    """
    Hassas rally madenciliği: Bir coin için tüm rallyleri bul.
    
    Args:
        symbol: Coin sembolü (BTCUSDT)
        timeframe: Zaman dilimi (15m, 1h, 4h)
        min_tier: Minimum tier (DIAMOND, GOLD, SILVER, BRONZE)
    
    Returns:
        List of PrecisionRally objects
    """
    # Veri yükle
    data_path = coin_cell_paths.get_history_file(symbol, timeframe)
    
    if not data_path.exists():
        logger.warning(f"Data not found: {data_path}")
        return []
    
    df = pd.read_parquet(data_path)
    
    # Timestamp index kontrolü
    if 'timestamp' not in df.columns:
        if 'open_time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['open_time'])
        else:
            df['timestamp'] = df.index
    
    df = df.reset_index(drop=True)
    
    # Minimum gain hesapla
    tier_thresholds = {
        "DIAMOND": 0.30,
        "GOLD": 0.20,
        "SILVER": 0.10,
        "BRONZE": 0.05,
    }
    min_gain = tier_thresholds.get(min_tier, 0.05)
    
    # Çoklu geçiş tespit
    logger.info(f"Mining {symbol} {timeframe} with min_tier={min_tier}...")
    raw_rallies = multi_pass_detection(df, min_gain=min_gain)
    
    logger.info(f"Found {len(raw_rallies)} raw rallies")
    
    # Her rally için rafine et
    precision_rallies = []
    
    for dip_idx, peak_idx, raw_gain in raw_rallies:
        # YOĞUN BÖLGE (Impulse Zone) bul
        impulse_start, impulse_end, impulse_gain = find_impulse_zone(df, dip_idx, peak_idx, window_size=10)
        
        # Giriş = Impulse başlangıcından 1 bar önce
        entry_idx = max(dip_idx, impulse_start - 1)
        entry_time = df.at[entry_idx, 'timestamp'] if 'timestamp' in df.columns else df.index[entry_idx]
        entry_price = df.at[entry_idx, 'close']
        
        # Çıkış = Impulse bitişi
        exit_idx = impulse_end
        exit_time = df.at[exit_idx, 'timestamp'] if 'timestamp' in df.columns else df.index[exit_idx]
        exit_price = df.at[exit_idx, 'close']
        
        # Rafine kazanç hesapla (entry/exit arası)
        if entry_price > 0:
            gain_pct = (exit_price - entry_price) / entry_price
        else:
            gain_pct = 0
        
        # Tier = HAM KAZANCA (dip-peak) göre hesapla, rafine değil!
        # Bu sayede eski sistemle aynı sayıda Diamond/Gold bulunur
        tier = compute_tier_from_gain_pct(raw_gain)
        
        # Minimum tier kontrolü
        if tier is None:
            continue
        
        tier_order = ["BRONZE", "SILVER", "GOLD", "DIAMOND"]
        if tier_order.index(tier) < tier_order.index(min_tier):
            continue
        
        # Impulse start/end zaman bilgileri (giriş/çıkış için kullanılıyor)
        impulse_start_time = df.at[impulse_start, 'timestamp'] if 'timestamp' in df.columns else df.index[impulse_start]
        
        rally = PrecisionRally(
            symbol=symbol,
            timeframe=timeframe,
            raw_dip_idx=dip_idx,
            raw_peak_idx=peak_idx,
            raw_gain_pct=raw_gain,  # Ham kazanç (tier için)
            entry_idx=entry_idx,
            entry_time=entry_time,
            entry_price=entry_price,
            exit_idx=exit_idx,
            exit_time=exit_time,
            exit_price=exit_price,
            breakout_idx=impulse_start,  # Impulse başlangıcı
            breakout_time=impulse_start_time,
            gain_pct=gain_pct,  # Rafine kazanç (gerçek trade için)
            bars_to_peak=peak_idx - dip_idx,  # Dip'ten peak'e bar sayısı (eski sistemle uyumlu)
            tier=tier,
        )
        
        precision_rallies.append(rally)
    
    logger.info(f"Final: {len(precision_rallies)} precision rallies (min_tier={min_tier})")
    
    return precision_rallies


def mine_diamond_gold_rallies(symbol: str, timeframe: str) -> List[PrecisionRally]:
    """Diamond ve Gold rallyleri bul."""
    all_rallies = mine_precision_rallies(symbol, timeframe, min_tier="GOLD")
    return [r for r in all_rallies if r.tier in ["DIAMOND", "GOLD"]]


# Test fonksiyonu
if __name__ == "__main__":
    # ADA test
    rallies = mine_diamond_gold_rallies("ADAUSDT", "15m")
    
    print(f"\n{'='*60}")
    print(f"ADAUSDT 15m - Diamond & Gold Rallies")
    print(f"{'='*60}")
    
    for r in rallies:
        print(f"\n{r.tier} Rally:")
        print(f"  Entry: {r.entry_time} @ {r.entry_price:.4f}")
        print(f"  Breakout: {r.breakout_time}")
        print(f"  Exit: {r.exit_time} @ {r.exit_price:.4f}")
        print(f"  Gain: {r.gain_pct*100:.1f}%")
        print(f"  Bars: {r.bars_to_peak}")
