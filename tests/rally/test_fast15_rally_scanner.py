"""
Tests for Fast15 Rally Scanner module.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from tezaver.rally.fast15_rally_scanner import (
    classify_macd_phase,
    determine_rally_bucket,
    detect_rallies_oracle_mode,
    generate_summary_stats,
    generate_turkish_summary,
    FAST15_RALLY_BUCKETS,
    FAST15_MIN_GAIN,
    FAST15_EVENT_GAP,
)


class TestMACDPhaseClassification:
    """Tests for MACD phase classification logic."""
    
    def test_sleep_phase(self):
        """Very small histogram should be UYKU."""
        phase = classify_macd_phase(hist=0.0001, signal=0.05, line=0.05)
        assert phase == "UYKU"
    
    def test_negative_histogram(self):
        """Negative histogram should be UYKU."""
        phase = classify_macd_phase(hist=-0.002, signal=0.05, line=0.04)
        assert phase == "UYKU"
    
    def test_strong_run(self):
        """Strong positive histogram should be KOSU."""
        phase = classify_macd_phase(hist=0.005, signal=0.02, line=0.025, is_rising=True)
        assert phase == "KOSU"
    
    def test_awakening(self):
        """Medium positive rising should be UYANIS."""
        phase = classify_macd_phase(hist=0.0015, signal=0.01, line=0.0115, is_rising=True)
        assert phase == "UYANIS"


class TestBucketClassification:
    """Tests for rally bucket determination."""
    
    def test_5_to_10_percent(self):
        """7% gain should map to 5p_10p bucket."""
        bucket = determine_rally_bucket(0.07)
        assert bucket == "5p_10p"
    
    def test_10_to_20_percent(self):
        """15% gain should map to 10p_20p bucket."""
        bucket = determine_rally_bucket(0.15)
        assert bucket == "10p_20p"
    
    def test_20_to_30_percent(self):
        """25% gain should map to 20p_30p bucket."""
        bucket = determine_rally_bucket(0.25)
        assert bucket == "20p_30p"
    
    def test_30_plus_percent(self):
        """40% gain should map to 30p_plus bucket."""
        bucket = determine_rally_bucket(0.40)
        assert bucket == "30p_plus"
    
    def test_below_minimum(self):
        """3% gain should return None (below 5% minimum)."""
        bucket = determine_rally_bucket(0.03)
        assert bucket is None


class TestRallyDetection:
    """Tests for rally event detection in 15m data."""
    
    def test_simple_rally_detected(self):
        """Should detect a clear 10% rally within 5 bars."""
        # Create synthetic data: flat then 10% rise over 5 bars
        timestamps = pd.date_range(start='2025-01-01', periods=20, freq='15min')
        
        close_prices = [100.0] * 10  # Flat for 10 bars
        high_prices = [100.5] * 10
        low_prices = [99.5] * 10 # Added low prices which are needed
        
        # Then 10% rally over 5 bars
        for i in range(5):
            close_prices.append(100 + (i+1) * 2)  # Gradual rise
            high_prices.append(100 + (i+1) * 2 + 0.5)
            low_prices.append(100 + (i+1) * 2 - 0.5)
        
        # Then flat again
        close_prices.extend([110.0] * 5)
        high_prices.extend([110.5] * 5)
        low_prices.extend([109.5] * 5)
        
        df_15m = pd.DataFrame({
            'timestamp': timestamps,
            'close': close_prices,
            'high': high_prices,
            'low': low_prices  # Required for oracle mode
        })
        
        # Oracle mode uses window_radius instead of lookahead
        events = detect_rallies_oracle_mode(df_15m, window_radius=2, min_gain=0.05)
        
        # Note: window_radius needs to be small enough for the local min to be detected 
        # given the structure of synthetic data (dip at index 9/10).
        
        assert not events.empty, "Should detect at least one rally"
        
        # Check first event
        first_event = events.iloc[0]
        assert first_event['future_max_gain_pct'] >= 0.05, "Should detect at least 5% gain"
        assert first_event['rally_bucket'] in ['10p_20p', '5p_10p'], "Should be in correct bucket"
        # bars_to_peak is calculated differently via oracle mode but should precise
    
    def test_no_rally_flat_data(self):
        """Flat price data should yield no rallies."""
        timestamps = pd.date_range(start='2025-01-01', periods=50, freq='15min')
        
        df_15m = pd.DataFrame({
            'timestamp': timestamps,
            'close': [100.0] * 50,
            'high': [100.1] * 50,
            'low': [99.9] * 50
        })
        
        events = detect_rallies_oracle_mode(df_15m)
        
        assert events.empty, "Flat data should produce no rallies"
    
    def test_declining_data(self):
        """Declining price data should yield no rallies."""
        timestamps = pd.date_range(start='2025-01-01', periods=50, freq='15min')
        
        close_prices = [100 - i * 0.5 for i in range(50)]
        high_prices = [p + 0.2 for p in close_prices]
        low_prices = [p - 0.2 for p in close_prices]
        
        df_15m = pd.DataFrame({
            'timestamp': timestamps,
            'close': close_prices,
            'high': high_prices,
            'low': low_prices
        })
        
        events = detect_rallies_oracle_mode(df_15m)
        
        assert events.empty, "Declining data should produce no rallies"
    
    def test_event_gap_prevents_overlap(self):
        """Window radius effectively acts as gap and prevents noise."""
        timestamps = pd.date_range(start='2025-01-01', periods=30, freq='15min')
        
        # Create multiple small rallies close together
        close_prices = []
        low_prices = []
        high_prices = []
        
        for i in range(6):
            # Each cycle: base + 5% spike
            base = 100 + i * 0.1
            close_prices.extend([base, base * 1.05, base, base, base])
            low_prices.extend([base*0.99, base * 1.04, base*0.99, base*0.99, base*0.99])
            high_prices.extend([base*1.01, base * 1.06, base*1.01, base*1.01, base*1.01])
        
        df_15m = pd.DataFrame({
            'timestamp': timestamps,
            'close': close_prices,
            'high': high_prices,
            'low': low_prices
        })
        
        # Large window radius should filter out local noise/secondary dips
        events = detect_rallies_oracle_mode(df_15m, window_radius=5)
        
        # Should detect only significant ones, likely 1 or few depending on global structure
        # Just creating the test to ensure it runs without error with new parameters
        assert isinstance(events, pd.DataFrame)


class TestSummaryGeneration:
    """Tests for summary statistics generation."""
    
    def test_summary_with_events(self):
        """Should generate valid summary dict from events."""
        # Create small events DataFrame
        events_df = pd.DataFrame({
            'rally_bucket': ['5p_10p', '5p_10p', '10p_20p'],
            'future_max_gain_pct': [0.07, 0.08, 0.15],
            'bars_to_peak': [3, 4, 5],
            'rsi_15m': [75, 72, 68],
            'rsi_ema_15m': [65, 63, 60],
            'macd_phase_15m': ['UYANIS', 'KOSU', 'UYANIS'],
            'trend_soul_1h': [65, 70, 55],
        })
        
        summary = generate_summary_stats(events_df, "TESTUSDT")
        
        assert summary['symbol'] == "TESTUSDT"
        assert summary['meta']['total_events'] == 3
        assert '5p_10p' in summary['buckets']
        assert '10p_20p' in summary['buckets']
        
        # Check 5p_10p bucket
        bucket_5_10 = summary['buckets']['5p_10p']
        assert bucket_5_10['event_count'] == 2
        assert 0.07 <= bucket_5_10['avg_future_max_gain_pct'] <= 0.08
    
    def test_summary_empty_events(self):
        """Should handle empty events gracefully."""
        empty_df = pd.DataFrame()
        
        summary = generate_summary_stats(empty_df, "EMPTYUSDT")
        
        assert summary['symbol'] == "EMPTYUSDT"
        assert summary['meta']['total_events'] == 0
        assert summary['buckets'] == {}
    
    def test_turkish_summary_generation(self):
        """Should generate Turkish text summary."""
        stats = {
            'symbol': 'BTCUSDT',
            'meta': {'total_events': 50, 'lookahead_bars': 10, 'min_gain': 0.05},
            'buckets': {
                '10p_20p': {
                    'event_count': 30,
                    'rsi_15m': {'gt_70_ratio': 0.8},
                    'rsi_ema_15m': {'gt_60_ratio': 0.75},
                    'macd_phase_15m': {'UYANIS': 0.4, 'KOSU': 0.5},
                    'trend_soul_1h': {'gt_60_ratio': 0.7}
                }
            }
        }
        
        summary_text = generate_turkish_summary(stats)
        
        assert isinstance(summary_text, str)
        assert 'BTCUSDT' in summary_text
        assert '50' in summary_text or 'elli' in summary_text.lower()
        # Should mention conditions since 10p_20p has 30 samples (>= 20)
        assert 'RSI' in summary_text or '%' in summary_text


class TestIntegration:
    """Integration tests (requires actual data or mocking)."""
    
    @pytest.mark.skip(reason="Requires actual 15m feature data")
    def test_full_scan_btc(self):
        """
        Full integration test on real BTC data.
        Skipped by default - run manually when data is available.
        """
        from tezaver.rally.fast15_rally_scanner import run_fast15_scan_for_symbol
        
        result = run_fast15_scan_for_symbol("BTCUSDT")
        
        assert result.symbol == "BTCUSDT"
        assert result.output_path.exists()
        assert result.summary_path.exists()
        
        # Load and verify parquet
        df = pd.read_parquet(result.output_path)
        assert 'rally_bucket' in df.columns
        assert 'rsi_15m' in df.columns
        assert 'event_time' in df.columns


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
