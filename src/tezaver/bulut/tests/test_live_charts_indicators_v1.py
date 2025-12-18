# Tezaver Bulut - Indicator Tests
"""
Tests for UI Chart Indicators.
"""
import pandas as pd
import numpy as np
import pytest
from tezaver.bulut.ui.chart_indicators import calculate_rsi, calculate_macd, calculate_atr, calculate_sma, calculate_ema

@pytest.fixture
def sample_data():
    # Simple recurring pattern
    prices = [10, 11, 12, 11, 10, 9, 10, 11, 12, 13, 14, 15, 14, 13, 12] * 5
    return pd.DataFrame({
        "close": pd.Series(prices),
        "high": pd.Series([x + 1 for x in prices]),
        "low": pd.Series([x - 1 for x in prices])
    })

def test_sma(sample_data):
    period = 5
    sma = calculate_sma(sample_data["close"], period)
    assert pd.isna(sma.iloc[period-2])
    assert not pd.isna(sma.iloc[period-1])
    # Manual calc last window
    last_window = sample_data["close"].iloc[-5:]
    expected = last_window.mean()
    assert np.isclose(sma.iloc[-1], expected)

def test_ema(sample_data):
    ema = calculate_ema(sample_data["close"], 5)
    # EMA has no hard NaN period with adjust=False usually, starts from first point
    assert not pd.isna(ema.iloc[0])

def test_rsi(sample_data):
    rsi = calculate_rsi(sample_data["close"], 14)
    # RSI should be between 0 and 100
    assert rsi.min() >= 0
    assert rsi.max() <= 100
    # Check NaN for warm up
    # With min_periods=14, first 13 might be NaN or approximated?
    # ewm usually starts outputting early, but we set min_periods
    # Actually ewm with min_periods will emit NaNs
    pass

def test_macd(sample_data):
    m, s, h = calculate_macd(sample_data["close"])
    assert len(m) == len(sample_data)
    # MACD = Fast - Slow. If Fast crosses Slow, MACD crosses 0.
    # Sanity check types
    assert isinstance(m, pd.Series)

def test_atr(sample_data):
    atr = calculate_atr(sample_data["high"], sample_data["low"], sample_data["close"])
    assert atr.min() > 0
    # TR matches roughly High-Low = 2.0 in our fixture
    # So ATR should be close to 2.0
    assert np.isclose(atr.iloc[-1], 2.0, atol=0.5)
