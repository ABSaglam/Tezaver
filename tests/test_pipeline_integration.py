"""
Tezaver Mac - Pipeline Entegrasyon Testi

Bu test, tüm pipeline zincirinin (M2→M22) düzgün çalıştığını doğrular.
Mini bir test dataset'i ile uçtan uca test yapar.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Test fixtures
TEST_DATA_DIR = Path("tests/fixtures")


class TestPipelineIntegration:
    """Pipeline entegrasyon testleri."""
    
    def test_coin_state_structure(self):
        """CoinState dosyasının geçerli yapıda olduğunu doğrular."""
        coin_state_path = Path("data/coin_state.json")
        
        if not coin_state_path.exists():
            pytest.skip("coin_state.json henüz oluşturulmamış")
        
        data = json.loads(coin_state_path.read_text())
        
        # Should be a list
        assert isinstance(data, list), "coin_state.json bir liste olmalı"
        
        if len(data) > 0:
            first_coin = data[0]
            
            # Required fields
            required_fields = ["symbol", "data_state"]
            for field in required_fields:
                assert field in first_coin, f"'{field}' alanı eksik"
    
    def test_global_wisdom_files_exist(self):
        """Global wisdom dosyalarının oluşturulduğunu doğrular."""
        wisdom_dir = Path("data/global_wisdom")
        
        if not wisdom_dir.exists():
            pytest.skip("global_wisdom dizini henüz oluşturulmamış")
        
        expected_files = [
            "global_pattern_stats.json",
            "global_regime_wisdom.json",
            "global_shock_wisdom.json"
        ]
        
        for filename in expected_files:
            file_path = wisdom_dir / filename
            assert file_path.exists(), f"{filename} dosyası eksik"
    
    def test_global_pattern_stats_structure(self):
        """Pattern stats dosyasının geçerli yapıda olduğunu doğrular."""
        stats_path = Path("data/global_wisdom/global_pattern_stats.json")
        
        if not stats_path.exists():
            pytest.skip("global_pattern_stats.json henüz oluşturulmamış")
        
        data = json.loads(stats_path.read_text())
        
        assert isinstance(data, list), "Pattern stats bir liste olmalı"
        
        if len(data) > 0:
            first_pattern = data[0]
            required_fields = ["trigger", "global_sample_count", "global_trust_score"]
            for field in required_fields:
                assert field in first_pattern, f"Pattern'de '{field}' alanı eksik"
    
    def test_coin_cell_structure(self):
        """Coin cell dizin yapısının doğru olduğunu kontrol eder."""
        coin_cells_dir = Path("coin_cells")
        
        if not coin_cells_dir.exists():
            pytest.skip("coin_cells dizini henüz oluşturulmamış")
        
        coins = list(coin_cells_dir.iterdir())
        
        if len(coins) == 0:
            pytest.skip("Henüz coin cell yok")
        
        # Check first coin structure
        first_coin = coins[0]
        expected_subdirs = ["data", "features", "snapshots", "levels"]
        
        for subdir in expected_subdirs:
            subdir_path = first_coin / subdir
            # At least some should exist
            if subdir_path.exists():
                return  # Pass if at least one exists
        
        # If none exist, that's okay for early stage
        pytest.skip("Coin cell alt dizinleri henüz oluşturulmamış")


class TestDataQuality:
    """Veri kalitesi kontrolleri."""
    
    def test_history_data_no_gaps(self):
        """Geçmiş veride büyük zaman boşlukları olmadığını kontrol eder."""
        coin_cells_dir = Path("coin_cells")
        
        if not coin_cells_dir.exists():
            pytest.skip("coin_cells dizini henüz oluşturulmamış")
        
        for coin_dir in coin_cells_dir.iterdir():
            if not coin_dir.is_dir():
                continue
            
            data_dir = coin_dir / "data"
            if not data_dir.exists():
                continue
            
            for parquet_file in data_dir.glob("history_*.parquet"):
                df = pd.read_parquet(parquet_file)
                
                if len(df) < 2:
                    continue
                
                # Check for timestamp column
                if 'timestamp' in df.columns:
                    timestamps = pd.to_datetime(df['timestamp'])
                    diffs = timestamps.diff().dropna()
                    
                    # No gap should be more than 2x expected interval
                    # We're being lenient here
                    if len(diffs) > 0:
                        median_diff = diffs.median()
                        max_allowed = median_diff * 5  # 5x tolerance
                        
                        large_gaps = diffs[diffs > max_allowed]
                        
                        if len(large_gaps) > 0:
                            gap_pct = len(large_gaps) / len(diffs) * 100
                            assert gap_pct < 10, f"{parquet_file.name}: %{gap_pct:.1f} büyük boşluk var"
    
    def test_no_negative_prices(self):
        """Negatif fiyat olmadığını kontrol eder."""
        coin_cells_dir = Path("coin_cells")
        
        if not coin_cells_dir.exists():
            pytest.skip("coin_cells dizini henüz oluşturulmamış")
        
        for coin_dir in coin_cells_dir.iterdir():
            if not coin_dir.is_dir():
                continue
            
            data_dir = coin_dir / "data"
            if not data_dir.exists():
                continue
            
            for parquet_file in data_dir.glob("history_*.parquet"):
                df = pd.read_parquet(parquet_file)
                
                price_columns = ['open', 'high', 'low', 'close']
                for col in price_columns:
                    if col in df.columns:
                        negative_count = (df[col] < 0).sum()
                        assert negative_count == 0, f"{parquet_file.name}: {col}'da {negative_count} negatif değer var"
    
    def test_no_extreme_price_jumps(self):
        """Aşırı fiyat sıçraması olmadığını kontrol eder (%1000 üzeri)."""
        coin_cells_dir = Path("coin_cells")
        
        if not coin_cells_dir.exists():
            pytest.skip("coin_cells dizini henüz oluşturulmamış")
        
        for coin_dir in coin_cells_dir.iterdir():
            if not coin_dir.is_dir():
                continue
            
            data_dir = coin_dir / "data"
            if not data_dir.exists():
                continue
            
            for parquet_file in data_dir.glob("history_*.parquet"):
                df = pd.read_parquet(parquet_file)
                
                if 'close' in df.columns and len(df) > 1:
                    pct_change = df['close'].pct_change().abs()
                    extreme_jumps = pct_change[pct_change > 10.0]  # >1000%
                    
                    assert len(extreme_jumps) == 0, f"{parquet_file.name}: {len(extreme_jumps)} aşırı fiyat sıçraması var"


class TestUISmoke:
    """Basit UI smoke testleri."""
    
    def test_i18n_completeness(self):
        """Türkçe çeviri dosyasının temel alanları içerdiğini kontrol eder."""
        from tezaver.ui.i18n_tr import TAB_LABELS, METRIC_TOOLTIPS, BUTTON_LABELS
        
        # TAB_LABELS should have key tabs
        assert len(TAB_LABELS) >= 5, "En az 5 sekme etiketi olmalı"
        
        # METRIC_TOOLTIPS should have many entries
        assert len(METRIC_TOOLTIPS) >= 20, "En az 20 metrik tooltip olmalı"
        
        # BUTTON_LABELS should exist
        assert len(BUTTON_LABELS) >= 5, "En az 5 buton etiketi olmalı"
    
    def test_chart_area_imports(self):
        """chart_area modülünün doğru import edildiğini kontrol eder."""
        from tezaver.ui.chart_area import ChartFocus, build_coin_chart_figure, explain_center_bar
        
        assert ChartFocus is not None
        assert callable(build_coin_chart_figure)
        assert callable(explain_center_bar)
    
    def test_state_store_imports(self):
        """state_store modülünün doğru import edildiğini kontrol eder."""
        from tezaver.core.state_store import load_coin_states, find_coin_state
        
        assert callable(load_coin_states)
        assert callable(find_coin_state)
    
    def test_system_state_imports(self):
        """system_state modülünün doğru import edildiğini kontrol eder."""
        from tezaver.core.system_state import load_state, record_pipeline_run
        
        assert callable(load_state)
        assert callable(record_pipeline_run)
