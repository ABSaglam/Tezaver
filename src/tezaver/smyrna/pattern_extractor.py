"""
Pattern Extractor - Rally DNA Çıkarıcı
=====================================

Bu modül, onaylanmış rallylerin "DNA'sını" çıkarır.
55 özellik (Phase 1): RSI, MACD, Fiyat, Hacim, EMAlar + Üst TF bağlamı.

KULLANIM:
---------
from tezaver.smyrna.pattern_extractor import PatternExtractor

extractor = PatternExtractor()
features = extractor.extract_rally_features(rally_id="BTCUSDT_DIAMOND_123")

OUTPUT:
-------
Pandas DataFrame: Her satır = 1 rally, Her sütun = 1 özellik
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from pathlib import Path
from tezaver.core.logging_utils import get_logger
from tezaver.smyrna.data_access import get_rally_context
from tezaver.smyrna.feature_engine import (
    calculate_rsi,
    calculate_ema,
    calculate_macd,
    calculate_on_balance_volume,
    extract_volume_features
)
from tezaver.features.indicator_engine import compute_macd_hist_color

logger = get_logger(__name__)


class PatternExtractor:
    """
    Rally DNA Çıkarıcı - 55 Özellik Extractor.
    """
    
    def __init__(self, lookback_bars: int = 7):
        """
        Args:
            lookback_bars: Kaç bar geriye bakacağız (default: 7)
        """
        self.lookback_bars = lookback_bars
        self.upper_tfs = ['1h', '4h', '1d']  # Üst zaman dilimleri
    
    def extract_rally_features(
        self,
        rally_id: str,
        symbol: str,
        timeframe: str,
        entry_time: pd.Timestamp
    ) -> Dict:
        """
        Tek bir rallinin tüm özelliklerini çıkarır.
        
        Args:
            rally_id: Rally ID
            symbol: Coin symbol (BTCUSDT)
            timeframe: Ana TF (15m)
            entry_time: Rally başlangıç zamanı
            
        Returns:
            Dict: Özellik adı -> değer
        """
        features = {}
        features['rally_id'] = rally_id
        features['symbol'] = symbol
        features['timeframe'] = timeframe
        features['entry_time'] = entry_time
        
        try:
            # 15m Ana TF features
            main_features = self._extract_main_tf_features(rally_id)
            features.update(main_features)
            
            # Üst TF features (1h, 4h, 1D)
            for upper_tf in self.upper_tfs:
                upper_features = self._extract_upper_tf_features(
                    rally_id, upper_tf
                )
                # Prefix ekle (örn: "1h_rsi")
                prefixed = {f"{upper_tf}_{k}": v for k, v in upper_features.items()}
                features.update(prefixed)
            
            return features
            
        except Exception as e:
            logger.error(f"Feature extraction failed for {rally_id}: {e}")
            return features
    
    def _extract_main_tf_features(self, rally_id: str) -> Dict:
        """15m ana TF'den 28 özellik çıkar."""
        
        # Rally context (T-60 → T-0)
        context = get_rally_context(
            rally_id=rally_id,
            lookback_bars=60
        )
        
        if context is None or context.empty:
            logger.warning(f"No context for rally {rally_id}")
            return {}
        
        # T-0 (entry) rally context içindeki son bar
        # (get_rally_context zaten T-0'a kadar kesmiş)
        entry_idx = len(context) - 1
        
        # Son 7 bar (T-7 → T-0)
        start_idx = max(0, entry_idx - self.lookback_bars + 1)
        window = context.iloc[start_idx:entry_idx + 1]
        
        if len(window) < self.lookback_bars:
            logger.warning(f"Insufficient data for {symbol}: {len(window)} bars")
            return {}
        
        features = {}
        
        # === A. MOMENTUM ===
        rsi = calculate_rsi(window, period=14, column='close')
        rsi_ema = rsi.ewm(span=9, adjust=False).mean()
        
        macd_result = calculate_macd(window, column='close')
        macd_line = macd_result['macd']
        signal_line = macd_result['signal']
        hist = macd_result['histogram']
        macd_color = compute_macd_hist_color(hist)
        
        features['rsi'] = rsi.iloc[-1]
        features['rsi_ema'] = rsi_ema.iloc[-1]
        features['rsi_slope'] = self._compute_slope(rsi)
        features['rsi_ema_slope'] = self._compute_slope(rsi_ema)
        features['macd'] = macd_line.iloc[-1]
        features['macd_signal'] = signal_line.iloc[-1]
        features['macd_hist'] = hist.iloc[-1]
        features['macd_hist_color'] = macd_color.iloc[-1]
        
        # === B. FİYAT & TREND ===
        close = window['close']
        features['price'] = close.iloc[-1]
        features['price_change_pct'] = ((close.iloc[-1] - close.iloc[0]) / close.iloc[0]) * 100
        features['price_slope'] = self._compute_slope(close)
        
        # EMAlar
        ema_9 = calculate_ema(window, period=9, column='close')
        ema_21 = calculate_ema(window, period=21, column='close')
        ema_50 = calculate_ema(window, period=50, column='close')
        ema_200 = calculate_ema(window, period=200, column='close')
        
        features['ema_9'] = ema_9.iloc[-1]
        features['ema_21'] = ema_21.iloc[-1]
        features['ema_50'] = ema_50.iloc[-1]
        features['ema_200'] = ema_200.iloc[-1]
        
        # Fiyat vs EMA sapmaları
        features['price_vs_ema9_pct'] = ((close.iloc[-1] - ema_9.iloc[-1]) / ema_9.iloc[-1]) * 100
        features['price_vs_ema21_pct'] = ((close.iloc[-1] - ema_21.iloc[-1]) / ema_21.iloc[-1]) * 100
        features['price_vs_ema50_pct'] = ((close.iloc[-1] - ema_50.iloc[-1]) / ema_50.iloc[-1]) * 100
        features['price_vs_ema200_pct'] = ((close.iloc[-1] - ema_200.iloc[-1]) / ema_200.iloc[-1]) * 100
        
        # Trend yönü
        features['trend_direction'] = self._compute_trend_direction(
            ema_9.iloc[-1], ema_21.iloc[-1], ema_50.iloc[-1]
        )
        
        # === C. HACİM ===
        volume = window['volume']
        vol_ma_20 = volume.rolling(20, min_periods=1).mean()
        
        features['volume'] = volume.iloc[-1]
        features['volume_ratio'] = volume.iloc[-1] / vol_ma_20.iloc[-1] if vol_ma_20.iloc[-1] > 0 else 1.0
        features['volume_slope'] = self._compute_slope(volume)
        features['volume_climax'] = 1 if features['volume_ratio'] >= 3.0 else 0
        
        # OBV
        obv = calculate_on_balance_volume(window)
        features['obv_change_pct'] = ((obv.iloc[-1] - obv.iloc[0]) / abs(obv.iloc[0])) * 100 if abs(obv.iloc[0]) > 0 else 0
        
        return features
    
    def _extract_upper_tf_features(self, rally_id: str, upper_timeframe: str) -> Dict:
        """Üst TFden 9 özellik çıkar (RSI, RSI-EMA, slopes, MACD, Trend)."""
        
        # Rally metadata'sını al
        from tezaver.core.rally_store import RallyStore
        from tezaver.core import coin_cell_paths
        
        store = RallyStore()
        rally_doc = store.get_rally(rally_id)
        
        if not rally_doc:
            return self._get_empty_upper_tf_features()
        
        symbol = rally_doc['symbol']
        event_time = pd.Timestamp(rally_doc['event_time'])
       
        # Üst TF dosyasını oku
        upper_tf_file = coin_cell_paths.get_history_file(symbol, upper_timeframe)
        
        if not upper_tf_file.exists():
            return self._get_empty_upper_tf_features()
        
        df_full = pd.read_parquet(upper_tf_file)
        
        if 'timestamp' in df_full.columns and df_full.index.name != 'timestamp':
            df_full = df_full.set_index('timestamp')
        
        df_full.index = pd.to_datetime(df_full.index)
        df_full = df_full.sort_index()
        
        # Üst TFde event_time'a kadar olan barlar
        valid_bars = df_full[df_full.index <= event_time]
        
        if len(valid_bars) < 3:
            return self._get_empty_upper_tf_features()
        
        # Son 7 bar al
        start_idx = max(0, len(valid_bars) - self.lookback_bars)
        window = valid_bars.iloc[start_idx:]
        
        if len(window) < 3:  # Minimum veri
            return self._get_empty_upper_tf_features()
        
        features = {}
        
        # RSI
        rsi = calculate_rsi(window, period=14, column='close')
        rsi_ema = rsi.ewm(span=9, adjust=False).mean()
        
        features['rsi'] = rsi.iloc[-1]
        features['rsi_ema'] = rsi_ema.iloc[-1]
        features['rsi_slope'] = self._compute_slope(rsi)
        features['rsi_ema_slope'] = self._compute_slope(rsi_ema)
        
        # MACD
        macd_result = calculate_macd(window, column='close')
        macd_line = macd_result['macd']
        signal_line = macd_result['signal']
        hist = macd_result['histogram']
        macd_color = compute_macd_hist_color(hist)
        
        features['macd'] = macd_line.iloc[-1]
        features['macd_signal'] = signal_line.iloc[-1]
        features['macd_hist'] = hist.iloc[-1]
        features['macd_hist_color'] = macd_color.iloc[-1]
        
        # Trend
        ema_9 = calculate_ema(window, period=9, column='close')
        ema_21 = calculate_ema(window, period=21, column='close')
        ema_50 = calculate_ema(window, period=50, column='close')
        
        features['trend_direction'] = self._compute_trend_direction(
            ema_9.iloc[-1], ema_21.iloc[-1], ema_50.iloc[-1]
        )
        
        return features
    
    def _get_empty_upper_tf_features(self) -> Dict:
        """Veri yoksa boş özellikler döndür."""
        return {
            'rsi': np.nan,
            'rsi_ema': np.nan,
            'rsi_slope': np.nan,
            'rsi_ema_slope': np.nan,
            'macd': np.nan,
            'macd_signal': np.nan,
            'macd_hist': np.nan,
            'macd_hist_color': 'gray',
            'trend_direction': 'unknown'
        }
    
    def _compute_slope(self, series: pd.Series) -> str:
        """
        Seri yükseliyor mu, düşüyor mu, yoksa düz mü?
        
        Returns:
            'rising', 'falling', 'flat'
        """
        if len(series) < 2:
            return 'flat'
        
        # Son 3 değerin ortalamasını al
        n = min(3, len(series))
        recent = series.iloc[-n:]
        first_val = recent.iloc[0]
        last_val = recent.iloc[-1]
        
        change_pct = ((last_val - first_val) / abs(first_val)) * 100 if first_val != 0 else 0
        
        if change_pct > 2:
            return 'rising'
        elif change_pct < -2:
            return 'falling'
        else:
            return 'flat'
    
    def _compute_trend_direction(self, ema9: float, ema21: float, ema50: float) -> str:
        """
        EMA hizasına göre trend yönü.
        
        Returns:
            'bullish', 'bearish', 'mixed'
        """
        if ema9 > ema21 > ema50:
            return 'bullish'
        elif ema9 < ema21 < ema50:
            return 'bearish'
        else:
            return 'mixed'
    

    
    def extract_batch(
        self,
        rallies: List[Dict]
    ) -> pd.DataFrame:
        """
        Birden fazla rally için toplu feature extraction.
        
        Args:
            rallies: List of rally dicts with keys: rally_id, symbol, timeframe, entry_time
            
        Returns:
            DataFrame: Her satır = 1 rally
        """
        logger.info(f"Extracting features for {len(rallies)} rallies...")
        
        all_features = []
        
        for i, rally in enumerate(rallies):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(rallies)}")
            
            features = self.extract_rally_features(
                rally_id=rally['rally_id'],
                symbol=rally['symbol'],
                timeframe=rally['timeframe'],
                entry_time=rally['entry_time']
            )
            
            if features:
                all_features.append(features)
        
        df = pd.DataFrame(all_features)
        logger.info(f"Extracted {len(df)} feature vectors with {len(df.columns)} features each")
        
        return df


def test_pattern_extractor():
    """Test feature extraction."""
    from tezaver.core.rally_store import RallyStore
    
    logger.info("Testing Pattern Extractor...")
    
    store = RallyStore()
    rallies = store.list_rallies(tier='DIAMOND', timeframe='15m', limit=5)
    
    if not rallies:
        logger.error("No Diamond rallies found!")
        return
    
    # Debug: Print first rally structure
    logger.info(f"Sample rally keys: {rallies[0].keys()}")
    
    extractor = PatternExtractor(lookback_bars=7)
    
    # Test single rally
    r = rallies[0]
    
    # Handle different possible key names
    entry_time_key = 'event_time' if 'event_time' in r else 'detected_at'
    
    features = extractor.extract_rally_features(
        rally_id=r['id'],
        symbol=r['symbol'],
        timeframe=r['timeframe'],
        entry_time=pd.Timestamp(r[entry_time_key])
    )
    
    logger.info(f"Sample Features ({len(features)} total):")
    for k, v in list(features.items())[:15]:
        logger.info(f"  {k}: {v}")
    
    # Test batch
    rally_list = [
        {
            'rally_id': r['id'],
            'symbol': r['symbol'],
            'timeframe': r['timeframe'],
            'entry_time': pd.Timestamp(r[entry_time_key])
        }
        for r in rallies
    ]
    
    df = extractor.extract_batch(rally_list)
    logger.info(f"\nBatch Result: {df.shape}")
    logger.info(f"Columns: {list(df.columns[:20])}")
    logger.info("\nTest PASSED ✅")


if __name__ == "__main__":
    test_pattern_extractor()
