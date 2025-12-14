"""
Test Card Builder Filters - Verify status/label/quality filtering works.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd
import json

import sys
sys.path.insert(0, str(Path(__file__).parents[2] / "src"))


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_dataset():
    """Create a mock dataset with 10 entries."""
    return pd.DataFrame({
        "symbol": ["BTCUSDT"] * 10,
        "timeframe": ["15m"] * 10,
        "event_idx": list(range(10)),
        "event_time": [f"2024-01-{i+1:02d} 10:00:00" for i in range(10)],
        "feat_rsi_15m": [30, 35, 40, 45, 50, 55, 60, 65, 70, 75],
        "feat_quality_score": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],  # Varying quality
        "feat_volume_rel_15m": [1.0] * 10,
        "feat_atr_pct_15m": [1.0] * 10,
        "future_max_gain_pct": [0.1] * 10,
    })


@pytest.fixture
def mock_annotations():
    """Create mock SniperAnnotation objects."""
    from tezaver.sniper.sniper_annotations import SniperAnnotation
    
    # 5 APPROVED+GOOD, 3 REVIEWED+UNCERTAIN, 2 PENDING+BAD
    return [
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="0", entry_bar_offset=0, status="APPROVED", label="GOOD"),
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="1", entry_bar_offset=0, status="APPROVED", label="GOOD"),
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="2", entry_bar_offset=0, status="APPROVED", label="GOOD"),
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="3", entry_bar_offset=0, status="APPROVED", label="GOOD"),
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="4", entry_bar_offset=0, status="APPROVED", label="GOOD"),
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="5", entry_bar_offset=0, status="REVIEWED", label="UNCERTAIN"),
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="6", entry_bar_offset=0, status="REVIEWED", label="UNCERTAIN"),
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="7", entry_bar_offset=0, status="REVIEWED", label="UNCERTAIN"),
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="8", entry_bar_offset=0, status="PENDING", label="BAD"),
        SniperAnnotation(symbol="BTCUSDT", timeframe="15m", event_id="9", entry_bar_offset=0, status="PENDING", label="BAD"),
    ]


@pytest.fixture
def mock_insights():
    """Create mock insights with no filtering."""
    return {
        "version": "sniper_pattern_insights_v1",
        "positive_rate": 0.25,
        "feature_bins": {},
        "top_features": [],
    }


# =============================================================================
# Tests
# =============================================================================

def test_builder_filters_reduce_source_count_by_status_label(mock_dataset, mock_annotations, mock_insights):
    """
    Test that status/label filters reduce source_count.
    With APPROVED+GOOD only, should get 5 entries (not 10).
    """
    from tezaver.sniper.sniper_strategy_card_builder import (
        SniperStrategyCardConfig,
        build_sniper_strategy_card_for_symbol_timeframe,
    )
    
    cfg = SniperStrategyCardConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        include_status=["APPROVED"],
        include_labels=["GOOD"],
        quality_floor_policy="OFF",  # No quality filtering for this test
    )
    
    with patch("tezaver.sniper.sniper_strategy_card_builder._load_sniper_dataset") as mock_load:
        with patch("tezaver.sniper.sniper_strategy_card_builder._load_or_compute_insights") as mock_insights_fn:
            with patch("tezaver.sniper.sniper_strategy_card_builder.SniperAnnotationRepository") as mock_repo_cls:
                mock_load.return_value = mock_dataset
                mock_insights_fn.return_value = mock_insights
                mock_repo_instance = MagicMock()
                mock_repo_instance.load_all.return_value = mock_annotations
                mock_repo_cls.return_value = mock_repo_instance
                
                card = build_sniper_strategy_card_for_symbol_timeframe("BTCUSDT", "15m", cfg)
    
    prov = card["provenance"]
    
    # 5 APPROVED+GOOD entries
    assert prov["source_count"] == 5, f"Expected source_count=5, got {prov['source_count']}"
    assert prov["total_entries"] == 10
    assert prov["drops"]["status_label_drop"] == 5


def test_builder_quality_floor_off_increases_source_count_vs_hard(mock_dataset, mock_annotations, mock_insights):
    """
    Test that quality_floor_policy=OFF includes more entries than HARD.
    With HARD at 50, entries with quality < 50 are dropped.
    """
    from tezaver.sniper.sniper_strategy_card_builder import (
        SniperStrategyCardConfig,
        build_sniper_strategy_card_for_symbol_timeframe,
    )
    
    # First, include all annotations to focus on quality floor
    all_status = ["APPROVED", "REVIEWED", "PENDING"]
    all_labels = ["GOOD", "UNCERTAIN", "BAD"]
    
    # Test with HARD quality floor at 50
    cfg_hard = SniperStrategyCardConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        include_status=all_status,
        include_labels=all_labels,
        quality_floor_policy="HARD",
        quality_floor_value=50.0,
    )
    
    # Test with OFF quality floor
    cfg_off = SniperStrategyCardConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        include_status=all_status,
        include_labels=all_labels,
        quality_floor_policy="OFF",
        quality_floor_value=0.0,
    )
    
    with patch("tezaver.sniper.sniper_strategy_card_builder._load_sniper_dataset") as mock_load:
        with patch("tezaver.sniper.sniper_strategy_card_builder._load_or_compute_insights") as mock_insights_fn:
            with patch("tezaver.sniper.sniper_strategy_card_builder.SniperAnnotationRepository") as mock_repo_cls:
                mock_load.return_value = mock_dataset
                mock_insights_fn.return_value = mock_insights
                mock_repo_instance = MagicMock()
                mock_repo_instance.load_all.return_value = mock_annotations
                mock_repo_cls.return_value = mock_repo_instance
                
                card_hard = build_sniper_strategy_card_for_symbol_timeframe("BTCUSDT", "15m", cfg_hard)
                card_off = build_sniper_strategy_card_for_symbol_timeframe("BTCUSDT", "15m", cfg_off)
    
    source_count_hard = card_hard["provenance"]["source_count"]
    source_count_off = card_off["provenance"]["source_count"]
    
    # Quality scores: [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    # With HARD >= 50: entries 4-9 (6 entries with quality 50, 60, 70, 80, 90, 100)
    # With OFF: all 10 entries
    assert source_count_off > source_count_hard, \
        f"OFF source_count ({source_count_off}) should be > HARD source_count ({source_count_hard})"
    assert source_count_off == 10
    assert source_count_hard == 6  # quality >= 50 (entries indexed 4-9)


def test_strict_ids_subset_of_source_ids(mock_dataset, mock_annotations, mock_insights):
    """
    Test that strict_entry_ids is always a subset of source_entry_ids.
    """
    from tezaver.sniper.sniper_strategy_card_builder import (
        SniperStrategyCardConfig,
        build_sniper_strategy_card_for_symbol_timeframe,
    )
    
    cfg = SniperStrategyCardConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        include_status=["APPROVED", "REVIEWED", "PENDING"],
        include_labels=["GOOD", "UNCERTAIN", "BAD"],
        quality_floor_policy="OFF",
    )
    
    with patch("tezaver.sniper.sniper_strategy_card_builder._load_sniper_dataset") as mock_load:
        with patch("tezaver.sniper.sniper_strategy_card_builder._load_or_compute_insights") as mock_insights_fn:
            with patch("tezaver.sniper.sniper_strategy_card_builder.SniperAnnotationRepository") as mock_repo_cls:
                mock_load.return_value = mock_dataset
                mock_insights_fn.return_value = mock_insights
                mock_repo_instance = MagicMock()
                mock_repo_instance.load_all.return_value = mock_annotations
                mock_repo_cls.return_value = mock_repo_instance
                
                card = build_sniper_strategy_card_for_symbol_timeframe("BTCUSDT", "15m", cfg)
    
    prov = card["provenance"]
    source_ids = set(prov["source_entry_ids"])
    strict_ids = set(prov["strict_entry_ids"])
    
    # All strict IDs must be in source IDs
    assert strict_ids.issubset(source_ids), \
        f"strict_ids not subset of source_ids: diff={strict_ids - source_ids}"
    
    # strict_count <= source_count
    assert prov["strict_count"] <= prov["source_count"]


def test_provenance_v23_structure(mock_dataset, mock_annotations, mock_insights):
    """
    Test that provenance has v2.3 structure with drops.
    """
    from tezaver.sniper.sniper_strategy_card_builder import (
        SniperStrategyCardConfig,
        build_sniper_strategy_card_for_symbol_timeframe,
    )
    
    cfg = SniperStrategyCardConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        include_status=["APPROVED"],
        include_labels=["GOOD"],
        quality_floor_policy="HARD",
        quality_floor_value=50.0,
    )
    
    with patch("tezaver.sniper.sniper_strategy_card_builder._load_sniper_dataset") as mock_load:
        with patch("tezaver.sniper.sniper_strategy_card_builder._load_or_compute_insights") as mock_insights_fn:
            with patch("tezaver.sniper.sniper_strategy_card_builder.SniperAnnotationRepository") as mock_repo_cls:
                mock_load.return_value = mock_dataset
                mock_insights_fn.return_value = mock_insights
                mock_repo_instance = MagicMock()
                mock_repo_instance.load_all.return_value = mock_annotations
                mock_repo_cls.return_value = mock_repo_instance
                
                card = build_sniper_strategy_card_for_symbol_timeframe("BTCUSDT", "15m", cfg)
    
    prov = card["provenance"]
    
    # Check v2.3 structure
    assert prov["version"] == "v2.3"
    assert "total_entries" in prov
    assert "drops" in prov
    assert "status_label_drop" in prov["drops"]
    assert "quality_floor_drop" in prov["drops"]
    assert "strict_window_drop" in prov["drops"]
    assert "annotation_stats" in prov
    assert prov["builder_version"] == "sniper_strategy_card_builder_v2.3"


def test_provenance_has_drop_breakdown(mock_dataset, mock_annotations, mock_insights):
    """
    Test that provenance has drop_breakdown field with bottleneck.
    """
    from tezaver.sniper.sniper_strategy_card_builder import (
        SniperStrategyCardConfig,
        build_sniper_strategy_card_for_symbol_timeframe,
    )
    
    cfg = SniperStrategyCardConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        include_status=["APPROVED", "REVIEWED", "PENDING"],
        include_labels=["GOOD", "UNCERTAIN", "BAD"],
        quality_floor_policy="HARD",
        quality_floor_value=50.0,
    )
    
    with patch("tezaver.sniper.sniper_strategy_card_builder._load_sniper_dataset") as mock_load:
        with patch("tezaver.sniper.sniper_strategy_card_builder._load_or_compute_insights") as mock_insights_fn:
            with patch("tezaver.sniper.sniper_strategy_card_builder.SniperAnnotationRepository") as mock_repo_cls:
                mock_load.return_value = mock_dataset
                mock_insights_fn.return_value = mock_insights
                mock_repo_instance = MagicMock()
                mock_repo_instance.load_all.return_value = mock_annotations
                mock_repo_cls.return_value = mock_repo_instance
                
                card = build_sniper_strategy_card_for_symbol_timeframe("BTCUSDT", "15m", cfg)
    
    prov = card["provenance"]
    
    # Check drop_breakdown exists
    assert "drop_breakdown" in prov
    db = prov["drop_breakdown"]
    assert "source_to_quality_drop" in db
    assert "quality_to_strict_drop" in db
    assert "source_to_strict_drop" in db
    assert "bottleneck" in db
    assert db["bottleneck"] in ["SOURCE_TO_QUALITY", "QUALITY_TO_STRICT", "TIE", "NONE"]


def test_drop_breakdown_counts_consistent(mock_dataset, mock_annotations, mock_insights):
    """
    Test that drop_breakdown counts are consistent:
    source_to_strict_drop == source_to_quality_drop + quality_to_strict_drop
    """
    from tezaver.sniper.sniper_strategy_card_builder import (
        SniperStrategyCardConfig,
        build_sniper_strategy_card_for_symbol_timeframe,
    )
    
    cfg = SniperStrategyCardConfig(
        symbol="BTCUSDT",
        timeframe="15m",
        include_status=["APPROVED", "REVIEWED", "PENDING"],
        include_labels=["GOOD", "UNCERTAIN", "BAD"],
        quality_floor_policy="HARD",
        quality_floor_value=50.0,
    )
    
    with patch("tezaver.sniper.sniper_strategy_card_builder._load_sniper_dataset") as mock_load:
        with patch("tezaver.sniper.sniper_strategy_card_builder._load_or_compute_insights") as mock_insights_fn:
            with patch("tezaver.sniper.sniper_strategy_card_builder.SniperAnnotationRepository") as mock_repo_cls:
                mock_load.return_value = mock_dataset
                mock_insights_fn.return_value = mock_insights
                mock_repo_instance = MagicMock()
                mock_repo_instance.load_all.return_value = mock_annotations
                mock_repo_cls.return_value = mock_repo_instance
                
                card = build_sniper_strategy_card_for_symbol_timeframe("BTCUSDT", "15m", cfg)
    
    db = card["provenance"]["drop_breakdown"]
    
    # Verify consistency
    assert db["source_to_strict_drop"] == db["source_to_quality_drop"] + db["quality_to_strict_drop"], \
        f"Inconsistent: {db['source_to_strict_drop']} != {db['source_to_quality_drop']} + {db['quality_to_strict_drop']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
