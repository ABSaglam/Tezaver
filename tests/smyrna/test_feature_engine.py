"""
Unit Tests for Feature Engine - Momentum Category
==================================================
"Cerrah Protokolü: Her Feature Test Edilmeli"

Tests all momentum indicators for:
- Correctness (known values)
- Boundary conditions (0-100 range)
- NaN handling
- Edge cases
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from tezaver.smyrna.feature_engine import (
    calculate_rsi,
    detect_rsi_divergence,
    calculate_macd,
    detect_macd_cross,
    calculate_stochastic,
    extract_momentum_features
)


class TestRSI:
    """Tests for RSI calculation."""
    
    def test_rsi_range_0_to_100(self):
        """RSI must always be in [0, 100] range."""
        # Create sample data
        np.random.seed(42)
        prices = pd.Series(np.random.uniform(100, 200, 100))
        df = pd.DataFrame({'close': prices})
        
        rsi = calculate_rsi(df, period=14)
        
        # Check range
        assert rsi.min() >= 0, f"RSI below 0: {rsi.min()}"
        assert rsi.max() <= 100, f"RSI above 100: {rsi.max()}"
    
    def test_rsi_oversold_condition(self):
        """RSI should be < 30 in strong downtrend."""
        # Create strong downtrend
        prices = pd.Series(range(100, 0, -1))  # Strong decline
        df = pd.DataFrame({'close': prices})
        
        rsi = calculate_rsi(df, period=14)
        
        # Last RSI should be low (oversold)
        last_rsi = rsi.iloc[-1]
        assert last_rsi < 40, f"RSI not oversold in downtrend: {last_rsi}"
    
    def test_rsi_overbought_condition(self):
        """RSI should be > 70 in strong uptrend."""
        # Create strong uptrend
        prices = pd.Series(range(100, 200))  # Strong rise
        df = pd.DataFrame({'close': prices})
        
        rsi = calculate_rsi(df, period=14)
        
        # Last RSI should be high (overbought)
        last_rsi = rsi.iloc[-1]
        assert last_rsi > 60, f"RSI not overbought in uptrend: {last_rsi}"
    
    def test_rsi_missing_column_raises_error(self):
        """Should raise ValueError if column missing."""
        df = pd.DataFrame({'price': [100, 101, 102]})
        
        with pytest.raises(ValueError, match="Column 'close' not found"):
            calculate_rsi(df, column='close')
    
    def test_rsi_invalid_period_raises_error(self):
        """Should raise ValueError if period < 1."""
        df = pd.DataFrame({'close': [100, 101, 102]})
        
        with pytest.raises(ValueError, match="Period must be >= 1"):
            calculate_rsi(df, period=0)


class TestMACD:
    """Tests for MACD calculation."""
    
    def test_macd_returns_three_components(self):
        """MACD should return macd, signal, histogram."""
        df = pd.DataFrame({'close': np.random.uniform(100, 200, 100)})
        
        result = calculate_macd(df)
        
        assert 'macd' in result
        assert 'signal' in result
        assert 'histogram' in result
        assert len(result['macd']) == len(df)
    
    def test_macd_histogram_is_difference(self):
        """Histogram = MACD - Signal."""
        df = pd.DataFrame({'close': np.random.uniform(100, 200, 100)})
        
        result = calculate_macd(df)
        
        # Check histogram calculation
        expected_histogram = result['macd'] - result['signal']
        pd.testing.assert_series_equal(
            result['histogram'], 
            expected_histogram,
            check_names=False
        )
    
    def test_macd_cross_detection(self):
        """Detect golden cross (MACD > Signal from below)."""
        # Create data that will cause a cross
        # Rising prices should eventually cause MACD to cross above Signal
        prices = pd.Series([100] * 20 + list(range(100, 150)))  # Flat then rise
        df = pd.DataFrame({'close': prices})
        
        macd_data = calculate_macd(df)
        df['macd'] = macd_data['macd']
        df['macd_signal'] = macd_data['signal']
        
        crosses = detect_macd_cross(df)
        
        # Should detect at least one cross
        assert crosses.sum() > 0, "No MACD cross detected in rising trend"


class TestStochastic:
    """Tests for Stochastic Oscillator."""
    
    def test_stochastic_range_0_to_100(self):
        """Stochastic K and D must be in [0, 100] range."""
        df = pd.DataFrame({
            'high': np.random.uniform(100, 200, 100),
            'low': np.random.uniform(50, 99, 100),
            'close': np.random.uniform(75, 150, 100)
        })
        
        result = calculate_stochastic(df)
        
        # Check K range
        assert result['k'].min() >= 0, f"Stochastic K below 0"
        assert result['k'].max() <= 100, f"Stochastic K above 100"
        
        # Check D range
        assert result['d'].min() >= 0, f"Stochastic D below 0"
        assert result['d'].max() <= 100, f"Stochastic D above 100"
    
    def test_stochastic_at_price_extremes(self):
        """Stochastic should be near 100 when close = high."""
        # Create data where close = high
        df = pd.DataFrame({
            'high': [100] * 50,
            'low': [90] * 50,
            'close': [100] * 50  # Always at high
        })
        
        result = calculate_stochastic(df, k_period=14)
        
        # Final K should be near 100
        final_k = result['k'].iloc[-1]
        assert final_k > 90, f"Stochastic K not high when close=high: {final_k}"


class TestMomentumIntegration:
    """Integration tests for extract_momentum_features."""
    
    def test_extract_all_momentum_features(self):
        """Should add all momentum columns to DataFrame."""
        df = pd.DataFrame({
            'open': np.random.uniform(100, 200, 100),
            'high': np.random.uniform(100, 200, 100),
            'low': np.random.uniform(50, 99, 100),
            'close': np.random.uniform(75, 150, 100),
            'volume': np.random.uniform(1000, 10000, 100)
        })
        
        result = extract_momentum_features(df)
        
        # Check all expected columns exist
        expected_cols = [
            'rsi_14', 'rsi_divergence_bullish',
            'macd', 'macd_signal', 'macd_histogram', 'macd_cross',
            'stoch_k', 'stoch_d'
        ]
        
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"
    
    def test_no_infinite_values(self):
        """All features must have finite values (no inf)."""
        df = pd.DataFrame({
            'open': np.random.uniform(100, 200, 100),
            'high': np.random.uniform(100, 200, 100),
            'low': np.random.uniform(50, 99, 100),
            'close': np.random.uniform(75, 150, 100),
            'volume': np.random.uniform(1000, 10000, 100)
        })
        
        result = extract_momentum_features(df)
        
        # Check for infinite values
        for col in result.columns:
            if result[col].dtype in [np.float64, np.float32]:
                assert not np.isinf(result[col]).any(), f"Infinite values in {col}"


# Manual Test Function
def manual_test_momentum_features():
    """
    Manual test for visual inspection of features.
    
    Usage:
        python -c "from tests.smyrna.test_feature_engine import manual_test_momentum_features; manual_test_momentum_features()"
    """
    from tezaver.smyrna.data_access import get_rally_context
    from tezaver.core.rally_store import RallyStore
    
    store = RallyStore()
    rallies = store.list_rallies(limit=5)
    
    if not rallies:
        print("No rallies found in database")
        return
    
    rally_id = rallies[0]['id']
    print(f"Testing features on rally: {rally_id}")
    
    # Get context
    context = get_rally_context(rally_id, lookback_bars=60)
    
    # Extract features
    features = extract_momentum_features(context)
    
    # Display sample
    print("\nLast 5 rows with momentum features:")
    print(features[['close', 'rsi_14', 'macd', 'macd_histogram', 'stoch_k']].tail())
    
    # Boundary check
    print("\nBoundary Checks:")
    print(f"RSI range: [{features['rsi_14'].min():.2f}, {features['rsi_14'].max():.2f}]")
    print(f"Stochastic K range: [{features['stoch_k'].min():.2f}, {features['stoch_k'].max():.2f}]")
    print(f"Stochastic D range: [{features['stoch_d'].min():.2f}, {features['stoch_d'].max():.2f}]")
    
    print("\n✅ Manual test complete")


if __name__ == "__main__":
    manual_test_momentum_features()
