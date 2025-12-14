# Full Replay Dataset Builder Tests
"""
Tests for rally_full_replay_builder module.
"""

import pytest
import pandas as pd
from pathlib import Path


class TestFullReplayDatasetBuilder:
    """Tests for full replay dataset building."""
    
    def test_build_full_replay_dataset_shape_btc(self):
        """Test building BTCUSDT 15m full replay dataset."""
        from tezaver.rally.rally_full_replay_builder import build_full_replay_bars_for_symbol_timeframe
        
        try:
            df = build_full_replay_bars_for_symbol_timeframe("BTCUSDT", "15m")
        except (FileNotFoundError, ValueError) as e:
            pytest.skip(f"Data not available: {e}")
        
        # Check basic shape
        assert len(df) > 0
        assert "ts" in df.columns
        
        # Check OHLCV columns
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in df.columns
    
    def test_full_replay_has_feature_columns(self):
        """Test that full replay dataset has feature columns."""
        from tezaver.rally.rally_full_replay_builder import build_full_replay_bars_for_symbol_timeframe
        
        try:
            df = build_full_replay_bars_for_symbol_timeframe("BTCUSDT", "15m")
        except (FileNotFoundError, ValueError) as e:
            pytest.skip(f"Data not available: {e}")
        
        # At least some feature columns should exist
        feature_cols = ["rsi_15m", "volume_rel_15m", "atr_pct_15m"]
        existing_features = [c for c in feature_cols if c in df.columns]
        assert len(existing_features) > 0, "No feature columns found"
    
    def test_full_replay_labels_sparse_not_empty(self):
        """Test that labels are sparse but not completely empty."""
        from tezaver.rally.rally_full_replay_builder import build_full_replay_bars_for_symbol_timeframe
        
        try:
            df = build_full_replay_bars_for_symbol_timeframe("BTCUSDT", "15m")
        except (FileNotFoundError, ValueError) as e:
            pytest.skip(f"Data not available: {e}")
        
        if "future_max_gain_pct" not in df.columns:
            pytest.skip("Label column not in dataset")
        
        label_count = df["future_max_gain_pct"].notna().sum()
        
        # Labels should be sparse (not every bar has a label)
        assert label_count < len(df), "Labels should be sparse"
        
        # But at least some bars should have labels
        assert label_count > 0, "At least some bars should have labels"
    
    def test_save_full_replay_creates_file(self, tmp_path):
        """Test that save creates parquet file."""
        from tezaver.rally.rally_full_replay_builder import (
            save_full_replay_bars_for_symbol_timeframe,
            build_full_replay_bars_for_symbol_timeframe,
        )
        
        try:
            # First check if source data exists
            _ = build_full_replay_bars_for_symbol_timeframe("BTCUSDT", "15m")
        except (FileNotFoundError, ValueError) as e:
            pytest.skip(f"Data not available: {e}")
        
        # Save to temp directory
        output_dir = tmp_path / "BTCUSDT" / "15m"
        path = save_full_replay_bars_for_symbol_timeframe(
            "BTCUSDT",
            "15m",
            output_dir=output_dir,
        )
        
        # Check file exists
        assert path.exists()
        assert path.suffix == ".parquet"
        
        # Read back and verify
        df = pd.read_parquet(path)
        assert len(df) > 0
        assert "ts" in df.columns


class TestPriceBarLoader:
    """Tests for price bar loading."""
    
    def test_load_price_bars_returns_dataframe(self):
        """Test that load_price_bars_for_symbol_timeframe returns DataFrame."""
        from tezaver.rally.rally_full_replay_builder import load_price_bars_for_symbol_timeframe
        
        try:
            df = load_price_bars_for_symbol_timeframe("BTCUSDT", "15m")
        except FileNotFoundError as e:
            pytest.skip(f"Data not available: {e}")
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_load_price_bars_has_timestamp(self):
        """Test that loaded bars have timestamp column."""
        from tezaver.rally.rally_full_replay_builder import load_price_bars_for_symbol_timeframe
        
        try:
            df = load_price_bars_for_symbol_timeframe("BTCUSDT", "15m")
        except FileNotFoundError as e:
            pytest.skip(f"Data not available: {e}")
        
        assert "timestamp" in df.columns


class TestPatternLabelLoader:
    """Tests for pattern label loading."""
    
    def test_load_pattern_labels_returns_dataframe(self):
        """Test that load_pattern_labels_for_symbol_timeframe returns DataFrame."""
        from tezaver.rally.rally_full_replay_builder import load_pattern_labels_for_symbol_timeframe
        
        try:
            df = load_pattern_labels_for_symbol_timeframe("BTCUSDT", "15m")
        except FileNotFoundError as e:
            pytest.skip(f"Data not available: {e}")
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
    
    def test_load_pattern_labels_has_timestamp(self):
        """Test that labels have timestamp for joining."""
        from tezaver.rally.rally_full_replay_builder import load_pattern_labels_for_symbol_timeframe
        
        try:
            df = load_pattern_labels_for_symbol_timeframe("BTCUSDT", "15m")
        except FileNotFoundError as e:
            pytest.skip(f"Data not available: {e}")
        
        assert "timestamp" in df.columns
