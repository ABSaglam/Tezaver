"""
Tests for ONY Tier Filtering Feature
=====================================

Tests the tier normalization and filtering logic added in ONY v1.1.
"""

import pytest
import pandas as pd
from src.tezaver.ui.ony_tab import normalize_tier, compute_tier_from_gain, TIERS


class TestNormalizeTier:
    """Test normalize_tier function with various inputs."""
    
    def test_normalize_tier_variants(self):
        """Test that different tier string variants normalize correctly."""
        # Diamond variants
        assert normalize_tier("diamond") == "DIAMOND"
        assert normalize_tier("DIAMOND") == "DIAMOND"
        assert normalize_tier("DIA") == "DIAMOND"
        assert normalize_tier("💎") == "DIAMOND"
        
        # Gold variants
        assert normalize_tier("gold") == "GOLD"
        assert normalize_tier("GOLD") == "GOLD"
        assert normalize_tier("GLD") == "GOLD"
        assert normalize_tier("🥇") == "GOLD"
        
        # Silver variants
        assert normalize_tier("silver") == "SILVER"
        assert normalize_tier("SILVER") == "SILVER"
        assert normalize_tier("SLV") == "SILVER"
        assert normalize_tier("🥈") == "SILVER"
        
        # Bronze variants
        assert normalize_tier("bronze") == "BRONZE"
        assert normalize_tier("BRONZE") == "BRONZE"
        assert normalize_tier("BRZ") == "BRONZE"
        assert normalize_tier("🥉") == "BRONZE"
    
    def test_normalize_tier_unknown(self):
        """Test that unknown/invalid tiers return None."""
        assert normalize_tier("unknown") is None
        assert normalize_tier("PLATINUM") is None
        assert normalize_tier("garbage") is None
        assert normalize_tier(None) is None
        assert normalize_tier(pd.NA) is None
        assert normalize_tier("") is None


class TestComputeTierFromGain:
    """Test compute_tier_from_gain function."""
    
    def test_tier_boundaries(self):
        """Test that gain percentages map to correct tiers."""
        # Diamond: >= 30%
        assert compute_tier_from_gain(0.30) == "DIAMOND"
        assert compute_tier_from_gain(0.50) == "DIAMOND"
        assert compute_tier_from_gain(1.00) == "DIAMOND"
        
        # Gold: >= 20%, < 30%
        assert compute_tier_from_gain(0.20) == "GOLD"
        assert compute_tier_from_gain(0.25) == "GOLD"
        assert compute_tier_from_gain(0.299) == "GOLD"
        
        # Silver: >= 10%, < 20%
        assert compute_tier_from_gain(0.10) == "SILVER"
        assert compute_tier_from_gain(0.15) == "SILVER"
        assert compute_tier_from_gain(0.199) == "SILVER"
        
        # Bronze: >= 5%, < 10%
        assert compute_tier_from_gain(0.05) == "BRONZE"
        assert compute_tier_from_gain(0.07) == "BRONZE"
        assert compute_tier_from_gain(0.099) == "BRONZE"
        
        # Too low: < 5%
        assert compute_tier_from_gain(0.04) is None
        assert compute_tier_from_gain(0.01) is None
        assert compute_tier_from_gain(0.00) is None
    
    def test_tier_null_handling(self):
        """Test that null/NA values return None."""
        assert compute_tier_from_gain(None) is None
        assert compute_tier_from_gain(pd.NA) is None


class TestTierFiltering:
    """Test tier counting and filtering logic."""
    
    def test_counts_and_filtering(self):
        """Test that tier counting and filtering work correctly with mixed data."""
        # Create fake events with mixed tiers and unknown
        events = [
            {"event_id": "1", "future_max_gain_pct": 0.35, "tier": None},  # Will be DIAMOND
            {"event_id": "2", "future_max_gain_pct": 0.25, "tier": None},  # Will be GOLD
            {"event_id": "3", "future_max_gain_pct": 0.15, "tier": None},  # Will be SILVER
            {"event_id": "4", "future_max_gain_pct": 0.07, "tier": None},  # Will be BRONZE
            {"event_id": "5", "future_max_gain_pct": 0.32, "tier": None},  # Will be DIAMOND
            {"event_id": "6", "future_max_gain_pct": 0.03, "tier": None},  # Will be None (too low)
            {"event_id": "7", "future_max_gain_pct": 0.22, "tier": None},  # Will be GOLD
        ]
        
        df = pd.DataFrame(events)
        
        # Compute tiers
        df['tier'] = df['future_max_gain_pct'].apply(compute_tier_from_gain)
        
        # Remove events without valid tier
        df_filtered = df[df['tier'].notna()].copy()
        
        # Count per tier
        tier_counts = {tier: len(df_filtered[df_filtered['tier'] == tier]) for tier in TIERS}
        
        # Verify counts
        assert tier_counts["DIAMOND"] == 2, "Should have 2 DIAMOND events"
        assert tier_counts["GOLD"] == 2, "Should have 2 GOLD events"
        assert tier_counts["SILVER"] == 1, "Should have 1 SILVER event"
        assert tier_counts["BRONZE"] == 1, "Should have 1 BRONZE event"
        
        # Verify filtering by tier
        diamond_events = df_filtered[df_filtered['tier'] == "DIAMOND"]
        assert len(diamond_events) == 2
        assert set(diamond_events['event_id']) == {"1", "5"}
        
        gold_events = df_filtered[df_filtered['tier'] == "GOLD"]
        assert len(gold_events) == 2
        assert set(gold_events['event_id']) == {"2", "7"}
        
        # Verify unknown/too-low events are excluded
        assert "6" not in df_filtered['event_id'].values, "Event 6 (too low gain) should be filtered out"


class TestCanonicalTierSync:
    """Test that ONY wrapper matches canonical tier implementation."""
    
    def test_canonical_tier_sync(self):
        """
        Verify ONY's compute_tier_from_gain() produces identical results
        to the canonical compute_tier_from_gain_pct() from rally_grade_cards.
        
        This test prevents threshold drift between ONY and canonical source.
        """
        from src.tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
        from src.tezaver.ui.ony_tab import compute_tier_from_gain
        
        # Test boundary values
        test_cases = [
            # (gain_pct, expected_tier)
            (0.50, "DIAMOND"),  # Well above diamond
            (0.30, "DIAMOND"),  # Exact diamond boundary
            (0.299, "GOLD"),    # Just below diamond
            (0.25, "GOLD"),     # Mid-gold
            (0.20, "GOLD"),     # Exact gold boundary
            (0.199, "SILVER"),  # Just below gold
            (0.15, "SILVER"),   # Mid-silver
            (0.10, "SILVER"),   # Exact silver boundary
            (0.099, "BRONZE"),  # Just below silver
            (0.07, "BRONZE"),   # Mid-bronze
            (0.05, "BRONZE"),   # Exact bronze boundary
            (0.049, None),      # Just below bronze (excluded)
            (0.03, None),       # Too low
            (0.00, None),       # Zero
        ]
        
        for gain, expected in test_cases:
            canonical_result = compute_tier_from_gain_pct(gain)
            ony_result = compute_tier_from_gain(gain)
            
            assert canonical_result == expected, \
                f"Canonical: gain={gain} should produce {expected}, got {canonical_result}"
            assert ony_result == expected, \
                f"ONY: gain={gain} should produce {expected}, got {ony_result}"
            assert canonical_result == ony_result, \
                f"DRIFT DETECTED: canonical={canonical_result} != ony={ony_result} at gain={gain}"
    
    def test_canonical_tier_null_handling(self):
        """Verify both implementations handle null/NA values identically."""
        from src.tezaver.rally.rally_grade_cards import compute_tier_from_gain_pct
        from src.tezaver.ui.ony_tab import compute_tier_from_gain
        
        canonical_none = compute_tier_from_gain_pct(None)
        ony_none = compute_tier_from_gain(None)
        assert canonical_none == ony_none == None
        
        canonical_na = compute_tier_from_gain_pct(pd.NA)
        ony_na = compute_tier_from_gain(pd.NA)
        assert canonical_na == ony_na == None

