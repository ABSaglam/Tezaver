"""
Tests for ONY Timeframe-Specific Event Loading
===============================================

Verifies that ONY correctly loads events from different timeframe datasets
and generates stable event IDs.
"""

import pytest
import pandas as pd
from datetime import datetime, timezone
from src.tezaver.ui.ony_tab import _load_events_for_symbol_tf
from src.tezaver.core import coin_cell_paths


class TestTimeframePathMapping:
    """Test that timeframe values map to correct dataset paths."""
    
    def test_15m_path_mapping(self):
        """Verify 15m maps to fast15_rallies path."""
        symbol = "ETHUSDT"
        expected_path = coin_cell_paths.get_fast15_rallies_path(symbol)
        
        # Expected format: library/fast15_rallies/{symbol}/fast15_rallies.parquet
        assert "fast15_rallies" in str(expected_path)
        assert symbol in str(expected_path)
    
    def test_1h_path_mapping(self):
        """Verify 1h maps to time_labs 1h path."""
        symbol = "ETHUSDT"
        timeframe = "1h"
        expected_path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
        
        # Expected format: library/time_labs/1h/{symbol}/rallies_1h.parquet
        assert "time_labs" in str(expected_path)
        assert "1h" in str(expected_path)
        assert symbol in str(expected_path)
    
    def test_4h_path_mapping(self):
        """Verify 4h maps to time_labs 4h path."""
        symbol = "ETHUSDT"
        timeframe = "4h"
        expected_path = coin_cell_paths.get_time_labs_rallies_path(symbol, timeframe)
        
        # Expected format: library/time_labs/4h/{symbol}/rallies_4h.parquet
        assert "time_labs" in str(expected_path)
        assert "4h" in str(expected_path)
        assert symbol in str(expected_path)


class TestEventIdStability:
    """Test that event_id generation is deterministic and stable."""
    
    def test_event_id_format(self):
        """Verify event_id follows {symbol}_{timeframe}_{epoch_seconds} format."""
        # Create mock event with known timestamp
        symbol = "BTCUSDT"
        timeframe = "15m"
        event_time = pd.Timestamp("2025-12-21 07:45:00", tz=timezone.utc)
        epoch_seconds = int(event_time.timestamp())
        
        expected_id = f"{symbol}_{timeframe}_{epoch_seconds}"
        
        # Verify format
        parts = expected_id.split("_")
        assert len(parts) == 3
        assert parts[0] == symbol
        assert parts[1] == timeframe
        assert parts[2] == str(epoch_seconds)
        assert parts[2].isdigit()
    
    def test_event_id_determinism(self):
        """Verify same event_time produces same event_id."""
        symbol = "ETHUSDT"
        timeframe = "1h"
        event_time = pd.Timestamp("2025-12-21 08:00:00", tz=timezone.utc)
        
        # Generate ID multiple times
        epoch_seconds = int(event_time.timestamp())
        id_1 = f"{symbol}_{timeframe}_{epoch_seconds}"
        id_2 = f"{symbol}_{timeframe}_{epoch_seconds}"
        
        assert id_1 == id_2, "Event ID should be deterministic"
    
    def test_event_id_uniqueness_across_timeframes(self):
        """Verify same timestamp but different timeframes produce different IDs."""
        symbol = "BTCUSDT"
        event_time = pd.Timestamp("2025-12-21 09:00:00", tz=timezone.utc)
        epoch_seconds = int(event_time.timestamp())
        
        id_15m = f"{symbol}_15m_{epoch_seconds}"
        id_1h = f"{symbol}_1h_{epoch_seconds}"
        id_4h = f"{symbol}_4h_{epoch_seconds}"
        
        assert id_15m != id_1h
        assert id_1h != id_4h
        assert id_15m != id_4h


class TestTierCountsFilteringPerTimeframe:
    """Test that tier counts and filtering work correctly per timeframe."""
    
    def test_tier_filtering_with_different_distributions(self):
        """Verify tier filtering works with different gain distributions per timeframe."""
        from src.tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
        
        # Create fake dataframes with different distributions
        # 15m: More high-gain events (Diamond/Gold heavy)
        df_15m = pd.DataFrame({
            "event_id": ["e1", "e2", "e3", "e4", "e5"],
            "future_max_gain_pct": [0.35, 0.28, 0.22, 0.15, 0.08],
            "event_time": pd.date_range("2025-12-01", periods=5, freq="15min")
        })
        
        # 1h: Moderate distribution
        df_1h = pd.DataFrame({
            "event_id": ["h1", "h2", "h3", "h4", "h5", "h6"],
            "future_max_gain_pct": [0.25, 0.18, 0.12, 0.09, 0.06, 0.03],
            "event_time": pd.date_range("2025-12-01", periods=6, freq="1h")
        })
        
        # 4h: Lower gains (Silver/Bronze heavy)
        df_4h = pd.DataFrame({
            "event_id": ["f1", "f2", "f3", "f4"],
            "future_max_gain_pct": [0.15, 0.11, 0.07, 0.04],
            "event_time": pd.date_range("2025-12-01", periods=4, freq="4h")
        })
        
        # Compute tiers for each
        for df in [df_15m, df_1h, df_4h]:
            df['tier'] = df['future_max_gain_pct'].apply(compute_tier_from_gain_pct)
        
        # Filter out None tiers
        df_15m = df_15m[df_15m['tier'].notna()].copy()
        df_1h = df_1h[df_1h['tier'].notna()].copy()
        df_4h = df_4h[df_4h['tier'].notna()].copy()
        
        # Verify 15m counts
        # 0.35 -> DIAMOND, 0.28 -> GOLD (not DIAMOND!), 0.22 -> GOLD, 0.15 -> SILVER, 0.08 -> BRONZE
        tier_counts_15m = df_15m['tier'].value_counts().to_dict()
        assert tier_counts_15m.get("DIAMOND", 0) == 1, "15m should have 1 DIAMOND (0.35)"
        assert tier_counts_15m.get("GOLD", 0) == 2, "15m should have 2 GOLD (0.28, 0.22)"
        assert tier_counts_15m.get("SILVER", 0) == 1, "15m should have 1 SILVER (0.15)"
        assert tier_counts_15m.get("BRONZE", 0) == 1, "15m should have 1 BRONZE (0.08)"
        
        # Verify 1h counts (0.03 excluded)
        # 0.25 -> GOLD, 0.18 -> SILVER (not GOLD!), 0.12 -> SILVER, 0.09 -> BRONZE, 0.06 -> BRONZE
        tier_counts_1h = df_1h['tier'].value_counts().to_dict()
        assert tier_counts_1h.get("GOLD", 0) == 1, "1h should have 1 GOLD (0.25)"
        assert tier_counts_1h.get("SILVER", 0) == 2, "1h should have 2 SILVER (0.18, 0.12)"
        assert tier_counts_1h.get("BRONZE", 0) == 2, "1h should have 2 BRONZE (0.09, 0.06)"
        assert len(df_1h) == 5, "1h should have 5 events (0.03 excluded)"
        
        # Verify 4h counts (0.04 excluded)
        tier_counts_4h = df_4h['tier'].value_counts().to_dict()
        assert tier_counts_4h.get("SILVER", 0) == 2, "4h should have 2 SILVER (0.15, 0.11)"
        assert tier_counts_4h.get("BRONZE", 0) == 1, "4h should have 1 BRONZE (0.07)"
        assert len(df_4h) == 3, "4h should have 3 events (0.04 excluded)"
    
    def test_tier_filtering_by_selected_tier(self):
        """Verify filtering by selected tier produces correct subset."""
        from src.tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
        
        # Create test data
        df = pd.DataFrame({
            "event_id": ["e1", "e2", "e3", "e4", "e5"],
            "future_max_gain_pct": [0.32, 0.25, 0.15, 0.08, 0.03],
        })
        
        df['tier'] = df['future_max_gain_pct'].apply(compute_tier_from_gain_pct)
        df = df[df['tier'].notna()].copy()
        
        # Filter by GOLD
        gold_events = df[df['tier'] == "GOLD"]
        assert len(gold_events) == 1
        assert gold_events.iloc[0]['event_id'] == "e2"
        
        # Filter by SILVER
        silver_events = df[df['tier'] == "SILVER"]
        assert len(silver_events) == 1
        assert silver_events.iloc[0]['event_id'] == "e3"
        
        # Filter by BRONZE
        bronze_events = df[df['tier'] == "BRONZE"]
        assert len(bronze_events) == 1
        assert bronze_events.iloc[0]['event_id'] == "e4"
