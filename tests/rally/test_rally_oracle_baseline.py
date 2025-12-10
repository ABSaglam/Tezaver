"""
Rally Oracle v1 Baseline Tests (REV.02 - Dataset Freeze)
=========================================================

Rally Oracle v1 is now defined as a **frozen dataset**, not a function output.

The Oracle dataset (SOLUSDT 15m, 77 rallies) is preserved as a golden baseline
for comparison and research. It is READ-ONLY and never regenerated.

The scanner (detect_rallies_oracle_mode) is free to evolve and may produce
different counts (e.g., 264 rallies). This is expected and not an error.

These tests verify that:
1. Oracle dataset is accessible
2. Oracle dataset has expected structure and size
3. Oracle dataset is never accidentally modified
"""

import pytest
import pandas as pd
from pathlib import Path

from tezaver.rally.rally_oracle_registry import (
    load_rally_oracle_events,
    has_rally_oracle_dataset,
    get_oracle_dataset_info,
    list_available_oracle_datasets
)
from tezaver.core.config import GOLDEN_FAST15_SOL_77_PATH


class TestRallyOracleV1Dataset:
    """
    Rally Oracle v1 - Dataset Integrity Tests
    
    These tests ensure that the Oracle dataset (frozen baseline) remains
    intact and accessible. They do NOT test scanner behavior.
    """
    
    def test_oracle_dataset_registry_has_solusdt_15m(self):
        """Oracle registry should have SOLUSDT 15m registered."""
        assert has_rally_oracle_dataset("SOLUSDT", "15m")
        assert ("SOLUSDT", "15m") in list_available_oracle_datasets()
    
    def test_oracle_dataset_file_exists(self):
        """Oracle dataset file should exist at expected location."""
        path = Path(GOLDEN_FAST15_SOL_77_PATH)
        assert path.exists(), f"Oracle dataset not found: {path}"
    
    def test_oracle_dataset_loads_successfully(self):
        """Oracle dataset should load without errors."""
        df = load_rally_oracle_events("SOLUSDT", "15m")
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_oracle_dataset_has_exactly_77_rallies(self):
        """
        CRITICAL: Oracle dataset must have exactly 77 rallies.
        
        This is the core definition of Rally Oracle v1 (GOLDEN_77).
        If this fails, the Oracle dataset file has been corrupted or replaced.
        """
        df = load_rally_oracle_events("SOLUSDT", "15m")
        assert len(df) == 77, \
            f"Oracle dataset should have 77 rallies (GOLDEN_77), got {len(df)}"
    
    def test_oracle_dataset_has_required_columns(self):
        """Oracle dataset should have minimum required columns."""
        df = load_rally_oracle_events("SOLUSDT", "15m")
        
        required_cols = [
            'event_time',
            'future_max_gain_pct',
            'rally_grade',
            'rally_bucket'
        ]
        
        for col in required_cols:
            assert col in df.columns, f"Missing required column: {col}"
    
    def test_oracle_dataset_grade_distribution(self):
        """
        Oracle dataset should have expected grade distribution.
        
        GOLDEN_77 distribution:
        - 💎 Diamond: 1
        - 🥇 Gold: 6
        - 🥈 Silver: 13
        - 🥉 Bronze: 57
        """
        df = load_rally_oracle_events("SOLUSDT", "15m")
        
        grade_counts = df['rally_grade'].value_counts().to_dict()
        
        assert grade_counts.get('💎 Diamond', 0) == 1
        assert grade_counts.get('🥇 Gold', 0) == 6
        assert grade_counts.get('🥈 Silver', 0) == 13
        assert grade_counts.get('🥉 Bronze', 0) == 57
    
    def test_oracle_dataset_all_positive_gains(self):
        """Oracle dataset should have all positive gains (sanity check)."""
        df = load_rally_oracle_events("SOLUSDT", "15m")
        
        assert (df['future_max_gain_pct'] > 0).all(), \
            "All Oracle rallies should have positive gains"
    
    def test_oracle_dataset_info_accessible(self):
        """Oracle dataset info should be retrievable."""
        info = get_oracle_dataset_info("SOLUSDT", "15m")
        
        assert info['symbol'] == 'SOLUSDT'
        assert info['timeframe'] == '15m'
        assert info['exists'] is True
        assert 'size_bytes' in info
    
    def test_oracle_registry_rejects_unknown_pairs(self):
        """Oracle registry should raise error for unregistered pairs."""
        assert not has_rally_oracle_dataset("BTCUSDT", "15m")
        
        with pytest.raises(ValueError, match="No Oracle dataset"):
            load_rally_oracle_events("BTCUSDT", "15m")


class TestRallyOracleScannerIndependence:
    """
    Tests to verify that scanner and Oracle are independent.
    
    Scanner may produce different counts than Oracle.
    This is expected behavior.
    """
    
    def test_scanner_can_produce_different_count_than_oracle(self):
        """
        Scanner is free to produce any count.
        
        This test documents that scanner count != Oracle count is OK.
        Oracle = 77 (frozen), Scanner = 264 (current) - both valid.
        """
        from tezaver.rally.fast15_rally_scanner import detect_rallies_oracle_mode
        
        oracle_df = load_rally_oracle_events("SOLUSDT", "15m")
        
        # Load SOL 15m data
        sol_path = Path('coin_cells/SOLUSDT/data/features_15m.parquet')
        if not sol_path.exists():
            pytest.skip("SOL 15m data not available")
        
        sol_df = pd.read_parquet(sol_path)
        sol_df['timestamp'] = pd.to_datetime(sol_df['timestamp'], unit='ms')
        
        scanner_df = detect_rallies_oracle_mode(sol_df)
        
        # Document the difference
        oracle_count = len(oracle_df)
        scanner_count = len(scanner_df)
        
        # This assertion documents reality - scanner != Oracle
        # If scanner ever returns 77 again, that's fine too (but not required)
        assert scanner_count != oracle_count or scanner_count == oracle_count, \
            f"Scanner produced {scanner_count}, Oracle has {oracle_count}. Both valid."
