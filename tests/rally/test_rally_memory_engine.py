"""
Tests for Rally Memory Engine
==============================

BTCUSDT 15 Dakika Rally Context Score v1 testleri.
"""

import pytest
import pandas as pd
import numpy as np

from tezaver.rally.rally_memory_engine import (
    SweetSpotRange,
    Btc15mSweetSpotConfig,
    DEFAULT_BTCUSDT_15M_SWEET_SPOTS,
    compute_metric_match_score,
    compute_rally_context_score_v1_for_row,
    add_rally_context_score_v1_column,
)


class TestSweetSpotRange:
    """SweetSpotRange dataclass testleri."""
    
    def test_creation(self):
        """SweetSpotRange oluşturulabilir."""
        sr = SweetSpotRange(lower=10.0, upper=20.0, soft_margin=2.0)
        assert sr.lower == 10.0
        assert sr.upper == 20.0
        assert sr.soft_margin == 2.0


class TestComputeMetricMatchScore:
    """compute_metric_match_score fonksiyonu testleri."""
    
    def test_value_inside_sweet_spot_returns_1(self):
        """Değer tatlı bölge içindeyse 1.0 döner."""
        ss = SweetSpotRange(lower=20.0, upper=40.0, soft_margin=5.0)
        
        # Tam ortada
        assert compute_metric_match_score(30.0, ss) == 1.0
        
        # Alt sınırda
        assert compute_metric_match_score(20.0, ss) == 1.0
        
        # Üst sınırda
        assert compute_metric_match_score(40.0, ss) == 1.0
        
    def test_value_in_soft_margin_returns_05(self):
        """Değer soft margin içindeyse 0.5 döner."""
        ss = SweetSpotRange(lower=20.0, upper=40.0, soft_margin=5.0)
        
        # Alt soft margin içinde (15 <= x < 20)
        assert compute_metric_match_score(17.0, ss) == 0.5
        assert compute_metric_match_score(15.0, ss) == 0.5
        
        # Üst soft margin içinde (40 < x <= 45)
        assert compute_metric_match_score(42.0, ss) == 0.5
        assert compute_metric_match_score(45.0, ss) == 0.5
        
    def test_value_outside_returns_0(self):
        """Değer tamamen dışarıdaysa 0.0 döner."""
        ss = SweetSpotRange(lower=20.0, upper=40.0, soft_margin=5.0)
        
        # Çok düşük
        assert compute_metric_match_score(10.0, ss) == 0.0
        assert compute_metric_match_score(14.9, ss) == 0.0
        
        # Çok yüksek
        assert compute_metric_match_score(50.0, ss) == 0.0
        assert compute_metric_match_score(45.1, ss) == 0.0
        
    def test_none_returns_0(self):
        """None değeri 0.0 döner."""
        ss = SweetSpotRange(lower=20.0, upper=40.0, soft_margin=5.0)
        assert compute_metric_match_score(None, ss) == 0.0
        
    def test_nan_returns_0(self):
        """NaN değeri 0.0 döner."""
        ss = SweetSpotRange(lower=20.0, upper=40.0, soft_margin=5.0)
        assert compute_metric_match_score(float('nan'), ss) == 0.0
        assert compute_metric_match_score(np.nan, ss) == 0.0


class TestComputeRallyContextScoreV1ForRow:
    """compute_rally_context_score_v1_for_row fonksiyonu testleri."""
    
    def test_all_metrics_inside_sweet_spot_returns_100(self):
        """Tüm metrikler tatlı bölge içinde → skor = 100."""
        row = {
            "rsi_15m": 30.0,        # inside [22.4, 41.0]
            "volume_rel_15m": 2.1,  # inside [1.96, 2.31]
            "atr_pct_15m": 1.0,     # inside [0.61, 1.54]
        }
        
        score = compute_rally_context_score_v1_for_row(row)
        assert score == 100.0
        
    def test_two_inside_one_soft_margin_returns_83(self):
        """2 metrik içeride, 1 soft margin'de → skor ≈ 83.33."""
        row = {
            "rsi_15m": 23.0,        # inside [22.4, 41.0]
            "volume_rel_15m": 2.2,  # inside [1.96, 2.31]
            "atr_pct_15m": 1.7,     # soft margin (1.54 < 1.7 <= 1.84)
        }
        
        score = compute_rally_context_score_v1_for_row(row)
        # scores = [1.0, 1.0, 0.5] → raw = 2.5 → normalized = 83.33...
        assert abs(score - 83.33) < 0.1
        
    def test_one_inside_two_outside_returns_33(self):
        """1 metrik içeride, 2 dışarıda → skor ≈ 33.33."""
        row = {
            "rsi_15m": 30.0,        # inside
            "volume_rel_15m": 5.0,  # outside (> 2.61)
            "atr_pct_15m": 3.0,     # outside (> 1.84)
        }
        
        score = compute_rally_context_score_v1_for_row(row)
        # scores = [1.0, 0.0, 0.0] → raw = 1.0 → normalized = 33.33...
        assert abs(score - 33.33) < 0.1
        
    def test_all_outside_returns_0(self):
        """Tüm metrikler dışarıda → skor = 0."""
        row = {
            "rsi_15m": 80.0,        # way outside
            "volume_rel_15m": 5.0,  # way outside
            "atr_pct_15m": 3.0,     # way outside
        }
        
        score = compute_rally_context_score_v1_for_row(row)
        assert score == 0.0
        
    def test_nan_values_handled_gracefully(self):
        """NaN değerler hata vermemeli, 0 katkı yapmalı."""
        row = {
            "rsi_15m": 30.0,        # inside → 1.0
            "volume_rel_15m": np.nan,  # NaN → 0.0
            "atr_pct_15m": None,    # None → 0.0
        }
        
        score = compute_rally_context_score_v1_for_row(row)
        # scores = [1.0, 0.0, 0.0] → 33.33
        assert abs(score - 33.33) < 0.1
        
    def test_pandas_series_works(self):
        """pandas Series ile de çalışmalı."""
        row = pd.Series({
            "rsi_15m": 30.0,
            "volume_rel_15m": 2.1,
            "atr_pct_15m": 1.0,
        })
        
        score = compute_rally_context_score_v1_for_row(row)
        assert score == 100.0


class TestAddRallyContextScoreV1Column:
    """add_rally_context_score_v1_column fonksiyonu testleri."""
    
    def test_adds_column_to_dataframe(self):
        """DataFrame'e yeni kolon ekler."""
        df = pd.DataFrame([
            {"rsi_15m": 30.0, "volume_rel_15m": 2.1, "atr_pct_15m": 1.0},
            {"rsi_15m": 80.0, "volume_rel_15m": 5.0, "atr_pct_15m": 3.0},
        ])
        
        result = add_rally_context_score_v1_column(df)
        
        assert "rally_context_score_v1" in result.columns
        assert result.iloc[0]["rally_context_score_v1"] == 100.0
        assert result.iloc[1]["rally_context_score_v1"] == 0.0
        
    def test_original_df_not_modified(self):
        """Orijinal DataFrame modifiye edilmez."""
        df = pd.DataFrame([
            {"rsi_15m": 30.0, "volume_rel_15m": 2.1, "atr_pct_15m": 1.0},
        ])
        
        result = add_rally_context_score_v1_column(df)
        
        assert "rally_context_score_v1" not in df.columns
        assert "rally_context_score_v1" in result.columns
        
    def test_custom_column_name(self):
        """Özel kolon adı kullanılabilir."""
        df = pd.DataFrame([
            {"rsi_15m": 30.0, "volume_rel_15m": 2.1, "atr_pct_15m": 1.0},
        ])
        
        result = add_rally_context_score_v1_column(df, column_name="custom_score")
        
        assert "custom_score" in result.columns
        assert "rally_context_score_v1" not in result.columns


class TestDefaultConfig:
    """DEFAULT_BTCUSDT_15M_SWEET_SPOTS testleri."""
    
    def test_default_config_values(self):
        """Default config doğru değerlere sahip."""
        cfg = DEFAULT_BTCUSDT_15M_SWEET_SPOTS
        
        assert cfg.rsi_15m.lower == 22.4
        assert cfg.rsi_15m.upper == 41.0
        assert cfg.rsi_15m.soft_margin == 5.0
        
        assert cfg.volume_rel_15m.lower == 1.96
        assert cfg.volume_rel_15m.upper == 2.31
        assert cfg.volume_rel_15m.soft_margin == 0.3
        
        assert cfg.atr_pct_15m.lower == 0.61
        assert cfg.atr_pct_15m.upper == 1.54
        assert cfg.atr_pct_15m.soft_margin == 0.3
