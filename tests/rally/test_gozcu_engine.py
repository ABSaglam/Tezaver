"""
GÖZCÜ Engine Test Suite

Tests hierarchical rally filtering logic.
"""

import pandas as pd
import pytest
from datetime import datetime
from tezaver.rally.gozcu_engine import (
    build_hierarchical_rallies,
    filter_rallies_by_parent_windows,
    get_gozcu_statistics
)


def test_gozcu_btc_real_data():
    """Test GÖZCÜ with real BTC data"""
    # Load real rallies
    rallies_4h = pd.read_parquet('library/time_labs/4h/BTCUSDT/rallies_4h.parquet')
    rallies_1h = pd.read_parquet('library/time_labs/1h/BTCUSDT/rallies_1h.parquet')
    rallies_15m = pd.read_parquet('library/fast15_rallies/BTCUSDT/fast15_rallies.parquet')
    
    # Ensure datetime
    for df in [rallies_4h, rallies_1h, rallies_15m]:
        df['event_time'] = pd.to_datetime(df['event_time'])
    
    # Build hierarchical structure
    rallies_4h_out, rallies_1h_filt, rallies_15m_filt = build_hierarchical_rallies(
        rallies_4h, rallies_1h, rallies_15m
    )
    
    # Assertions
    assert len(rallies_4h_out) == len(rallies_4h), "4h rallies should be unchanged"
    assert len(rallies_1h_filt) <= len(rallies_1h), "1h rallies should be filtered"
    assert len(rallies_15m_filt) <= len(rallies_15m), "15m rallies should be filtered"
    
    # Check parent columns exist
    if not rallies_1h_filt.empty:
        assert 'parent_4h_rally_id' in rallies_1h_filt.columns
        assert 'parent_4h_rally_start' in rallies_1h_filt.columns
    
    if not rallies_15m_filt.empty:
        assert 'parent_1h_rally_id' in rallies_15m_filt.columns
        assert 'parent_1h_rally_start' in rallies_15m_filt.columns
        assert 'parent_4h_rally_id' in rallies_15m_filt.columns
    
    print(f"✅ 4h: {len(rallies_4h_out)} (unchanged)")
    print(f"✅ 1h: {len(rallies_1h)} → {len(rallies_1h_filt)} (filtered)")
    print(f"✅ 15m: {len(rallies_15m)} → {len(rallies_15m_filt)} (filtered)")


def test_dec2_rally_preservation():
    """Test that Dec 2 rally is preserved after GÖZCÜ filtering"""
    # Load real data
    rallies_4h = pd.read_parquet('library/time_labs/4h/BTCUSDT/rallies_4h.parquet')
    rallies_1h = pd.read_parquet('library/time_labs/1h/BTCUSDT/rallies_1h.parquet')
    rallies_15m = pd.read_parquet('library/fast15_rallies/BTCUSDT/fast15_rallies.parquet')
    
    for df in [rallies_4h, rallies_1h, rallies_15m]:
        df['event_time'] = pd.to_datetime(df['event_time'])
    
    # Apply GÖZCÜ
    _, _, rallies_15m_filt = build_hierarchical_rallies(
        rallies_4h, rallies_1h, rallies_15m
    )
    
    # Check Dec 2 rally
    dec2 = pd.Timestamp('2025-12-02')
    dec3 = pd.Timestamp('2025-12-03')
    
    dec2_rallies_orig = rallies_15m[
        (rallies_15m['event_time'] >= dec2) & 
        (rallies_15m['event_time'] < dec3)
    ]
    
    dec2_rallies_filt = rallies_15m_filt[
        (rallies_15m_filt['event_time'] >= dec2) & 
        (rallies_15m_filt['event_time'] < dec3)
    ]
    
    print(f"Dec 2 - Original: {len(dec2_rallies_orig)} rally")
    print(f"Dec 2 - GÖZCÜ: {len(dec2_rallies_filt)} rally")
    
    assert len(dec2_rallies_filt) > 0, "Dec 2 rally must be preserved!"
    print("✅ Dec 2 rally preserved")


def test_quality_improvement():
    """Test that GÖZCÜ improves average rally quality"""
    rallies_4h = pd.read_parquet('library/time_labs/4h/BTCUSDT/rallies_4h.parquet')
    rallies_1h = pd.read_parquet('library/time_labs/1h/BTCUSDT/rallies_1h.parquet')
    rallies_15m = pd.read_parquet('library/fast15_rallies/BTCUSDT/fast15_rallies.parquet')
    
    for df in [rallies_4h, rallies_1h, rallies_15m]:
        df['event_time'] = pd.to_datetime(df['event_time'])
    
    _, _, rallies_15m_filt = build_hierarchical_rallies(
        rallies_4h, rallies_1h, rallies_15m
    )
    
    # Calculate avg gain
    avg_orig = rallies_15m['future_max_gain_pct'].mean() * 100
    avg_filt = rallies_15m_filt['future_max_gain_pct'].mean() * 100
    
    print(f"Average gain - Original: {avg_orig:.2f}%")
    print(f"Average gain - GÖZCÜ: {avg_filt:.2f}%")
    
    assert avg_filt > avg_orig, "GÖZCÜ should improve average quality!"
    print(f"✅ Quality improved: {avg_orig:.2f}% → {avg_filt:.2f}%")


def test_no_high_gain_loss():
    """Test that no >10% rallies are lost"""
    rallies_4h = pd.read_parquet('library/time_labs/4h/BTCUSDT/rallies_4h.parquet')
    rallies_1h = pd.read_parquet('library/time_labs/1h/BTCUSDT/rallies_1h.parquet')
    rallies_15m = pd.read_parquet('library/fast15_rallies/BTCUSDT/fast15_rallies.parquet')
    
    for df in [rallies_4h, rallies_1h, rallies_15m]:
        df['event_time'] = pd.to_datetime(df['event_time'])
    
    _, _, rallies_15m_filt = build_hierarchical_rallies(
        rallies_4h, rallies_1h, rallies_15m
    )
    
    # Find high-gain rallies
    high_gain_orig = rallies_15m[rallies_15m['future_max_gain_pct'] >= 0.10]
    
    # Check if any are lost
    lost_high_gain = []
    for _, rally in high_gain_orig.iterrows():
        found = rallies_15m_filt[rallies_15m_filt['event_time'] == rally['event_time']]
        if found.empty:
            lost_high_gain.append(rally)
    
    print(f"High-gain (>10%) rallies in original: {len(high_gain_orig)}")
    print(f"High-gain rallies lost: {len(lost_high_gain)}")
    
    assert len(lost_high_gain) == 0, "No >10% rallies should be lost!"
    print("✅ All high-gain rallies preserved")


if __name__ == '__main__':
    print("=== GÖZCÜ ENGINE TESTS ===\n")
    
    print("Test 1: Real BTC Data")
    test_gozcu_btc_real_data()
    print()
    
    print("Test 2: Dec 2 Rally Preservation")
    test_dec2_rally_preservation()
    print()
    
    print("Test 3: Quality Improvement")
    test_quality_improvement()
    print()
    
    print("Test 4: No High-Gain Loss")
    test_no_high_gain_loss()
    print()
    
    print("=== ALL TESTS PASSED ===")
