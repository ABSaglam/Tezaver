"""
Rally Detector v2 - Multi-Coin Eval Tests
=========================================

Tests for the V2 evaluation module (REV.04).
Verifies that we can run V2 booster on multiple coins and generate/save stats.
"""

import pytest
import pandas as pd
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from tezaver.rally.rally_detector_v2_eval import (
    run_v2_eval_for_symbol, 
    save_v2_eval_stats, 
    load_v2_eval_stats,
    V2_STATS_DIR
)
from tezaver.rally.rally_detector_v2 import detect_rallies_v2_micro_booster


class TestRallyDetectorV2Eval:
    
    @pytest.fixture
    def mock_sol_data(self):
        """Create a mock DataFrame mimicking SOL 15m data."""
        # Using a simplistic mock for functional test
        # In real integration test we use actual parquet files
        path = Path('coin_cells/SOLUSDT/data/features_15m.parquet')
        if path.exists():
            df = pd.read_parquet(path)
            # Ensure timestamps are datetime
            if 'timestamp' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        else:
            # Fallback mock if real data missing (shouldn't happen in this env but safe)
            pytest.skip("SOL 15m data not found for eval test")

    def test_run_v2_eval_returns_valid_stats_structure(self, mock_sol_data):
        """
        Test that run_v2_eval_for_symbol returns a dictionary with expected keys.
        """
        # We need to ensure load_15m_features returns our mock data OR works with real data
        # Since we are using real integration environment, let's just run it on SOLUSDT
        # assuming the file exists (checked in fixture)
        
        result = run_v2_eval_for_symbol("SOLUSDT", "15m")
        
        assert result["symbol"] == "SOLUSDT"
        assert result["timeframe"] == "15m"
        assert "event_count" in result
        assert isinstance(result["event_count"], int)
        
        # Assuming defaults find some events on SOL (we know they do from previous tests)
        if result["event_count"] > 0:
            assert "gain_stats" in result
            assert "min" in result["gain_stats"]
            assert "mean" in result["gain_stats"]
            
            assert "gain_bucket_counts" in result
            assert "5_to_10" in result["gain_bucket_counts"]
            
            assert "bars_stats" in result

    def test_save_and_load_stats_roundtrip(self, tmp_path):
        """
        Test saving stats to JSON and loading them back.
        """
        symbol = "TESTCOIN"
        fake_stats = {
            "symbol": symbol,
            "timeframe": "15m",
            "event_count": 42,
            "gain_stats": {"mean": 0.07},
            "test_run": True
        }
        
        # Patch the global V2_STATS_DIR to use tmp_path for this test
        with patch("tezaver.rally.rally_detector_v2_eval.V2_STATS_DIR", tmp_path):
            file_path = save_v2_eval_stats(symbol, fake_stats)
            
            assert file_path.exists()
            assert file_path.name == "TESTCOIN_v2_stats.json"
            
            loaded_stats = load_v2_eval_stats(symbol)
            
            assert loaded_stats is not None
            assert loaded_stats["symbol"] == symbol
            assert loaded_stats["event_count"] == 42
            assert loaded_stats["gain_stats"]["mean"] == 0.07

    def test_run_v2_eval_respects_timeframe_check(self):
        """
        Verify that only '15m' timeframe is accepted.
        """
        with pytest.raises(ValueError):
            run_v2_eval_for_symbol("BTCUSDT", "1h")

    def test_eval_does_not_affect_oracle(self):
        """
        Sanity check: Running eval should not touch Oracle Registry.
        """
        from tezaver.rally.rally_oracle_registry import load_rally_oracle_events
        
        # Ensure Oracle is still 77
        try:
            oracle_df = load_rally_oracle_events("SOLUSDT", "15m")
            initial_len = len(oracle_df)
            assert initial_len == 77
            
            # Run eval
            run_v2_eval_for_symbol("SOLUSDT", "15m")
            
            # Check Oracle again
            oracle_df_after = load_rally_oracle_events("SOLUSDT", "15m")
            assert len(oracle_df_after) == 77
        except FileNotFoundError:
            # If oracle file missing in this env (shouldn't be), skip
            pytest.skip("Oracle file not found for protection check")

