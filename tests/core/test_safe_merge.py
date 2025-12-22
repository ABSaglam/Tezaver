"""
Tests for safe_merge_features functionality.
"""
import pytest
import pandas as pd
from tezaver.core.dataframe_utils import safe_merge_features

def test_safe_merge_exact_success():
    """Test exact merge works"""
    bars = pd.DataFrame({
        'open_time': [pd.Timestamp("2023-01-01 10:00"), pd.Timestamp("2023-01-01 10:15")],
        'close': [100, 101]
    })
    feats = pd.DataFrame({
        'open_time': [pd.Timestamp("2023-01-01 10:00"), pd.Timestamp("2023-01-01 10:15")],
        'rsi': [50, 55]
    })
    
    merged, diag = safe_merge_features(bars, feats)
    assert diag['mode'] == 'exact'
    assert len(merged) == 2
    assert merged['rsi'].notna().all()

def test_safe_merge_fallback_empty_feats():
    """Test fallback when features empty"""
    bars = pd.DataFrame({'open_time': [pd.Timestamp("2023-01-01")], 'close': [100]})
    feats = pd.DataFrame()
    
    merged, diag = safe_merge_features(bars, feats)
    assert diag['msg'] == "Features empty"
    assert len(merged) == 1
    assert 'rsi' not in merged.columns

def test_safe_merge_asof_recovery():
    """Test ASOF merge when exact fails (time mismatch)"""
    # Bars at 10:00, 10:15
    bars = pd.DataFrame({
        'open_time': [pd.Timestamp("2023-01-01 10:00"), pd.Timestamp("2023-01-01 10:15")],
        'close': [100, 101]
    })
    # Features shifted by 1 minute (10:01, 10:16)
    # Exact merge would yield null RSI. safe_merge should switch to ASOF.
    feats = pd.DataFrame({
        'open_time': [pd.Timestamp("2023-01-01 10:01"), pd.Timestamp("2023-01-01 10:16")],
        'rsi': [50, 55]
    })
    
    merged, diag = safe_merge_features(bars, feats)
    assert diag['mode'] == 'asof'
    assert len(merged) == 2
    assert merged['rsi'].notna().all()

def test_safe_merge_fallback_total_mismatch():
    """Test fallback when even asof fails (too far apart)"""
    bars = pd.DataFrame({'open_time': [pd.Timestamp("2023-01-01 10:00")], 'close': [100]})
    # Feature 2 hours away (tolerance 15m)
    feats = pd.DataFrame({'open_time': [pd.Timestamp("2023-01-01 12:00")], 'rsi': [50]})
    
    merged, diag = safe_merge_features(bars, feats)
    assert diag['mode'] == 'fallback'
    assert len(merged) == 1
    assert 'rsi' not in merged.columns # Fallback returns original bars (normalized)
