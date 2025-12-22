"""
Test Dataframe Utils - ensure_open_time
"""
import pytest
import pandas as pd
from tezaver.core.dataframe_utils import ensure_open_time

def test_ensure_open_time_from_column():
    """Test when open_time column exists"""
    df = pd.DataFrame({
        'open_time': [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")],
        'close': [100, 101]
    })
    
    result = ensure_open_time(df)
    assert 'open_time' in result.columns
    assert result['open_time'].equals(df['open_time'])
    assert result['open_time'].dt.tz is None

def test_ensure_open_time_from_alt_columns():
    """Test variants like timestamp, open_ts"""
    # Case 1: timestamp
    df1 = pd.DataFrame({
        'timestamp': [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02", tz="UTC")],
        'close': [10, 11]
    })
    res1 = ensure_open_time(df1)
    assert 'open_time' in res1.columns
    assert res1['open_time'].dt.tz is None
    
    # Case 2: date
    df2 = pd.DataFrame({
        'date': ["2023-01-01", "2023-01-02"],
        'close': [20, 21]
    })
    res2 = ensure_open_time(df2)
    assert 'open_time' in res2.columns
    assert pd.api.types.is_datetime64_any_dtype(res2['open_time'])

def test_ensure_open_time_from_index():
    """Test when time is in index"""
    idx = pd.DatetimeIndex(["2023-01-01", "2023-01-02"], tz="Europe/Istanbul")
    df = pd.DataFrame({'close': [50, 51]}, index=idx)
    
    result = ensure_open_time(df)
    assert 'open_time' in result.columns
    assert result['open_time'].dt.tz is None
    assert len(result) == 2

def test_ensure_open_time_merge_compat():
    """Test that two dfs normalized this way can merge"""
    df_bars = pd.DataFrame({
        'open_time': [pd.Timestamp("2023-01-01"), pd.Timestamp("2023-01-02")],
        'price': [100, 101]
    })
    
    df_feats = pd.DataFrame({
        'timestamp': [pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2023-01-02", tz="UTC")],
        'rsi': [50, 55]
    })
    
    norm_bars = ensure_open_time(df_bars)
    norm_feats = ensure_open_time(df_feats)
    
    merged = pd.merge(norm_bars, norm_feats, on='open_time', how='left')
    assert len(merged) == 2
    assert not merged['rsi'].isnull().any()
