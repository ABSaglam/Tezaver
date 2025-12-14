# Silver 15m Full Replay Tests
"""
Tests for full replay mode in Silver War Game.
"""

import pytest
import pandas as pd
from pathlib import Path

from tezaver.matrix.wargame.replay_datafeed import ReplayDataFeed


class TestFullReplayDataFeed:
    """Tests for from_symbol_timeframe_full_replay and from_dataframe_full_replay."""
    
    def test_from_dataframe_full_replay_creates_feed(self):
        """Test creating feed from fake DataFrame."""
        fake_df = pd.DataFrame({
            "ts": ["2023-01-01 00:00:00", "2023-01-01 00:15:00", "2023-01-01 00:30:00"],
            "open": [42000.0, 42100.0, 42200.0],
            "high": [42100.0, 42200.0, 42300.0],
            "low": [41900.0, 42000.0, 42100.0],
            "close": [42050.0, 42150.0, 42250.0],
            "volume": [100.0, 110.0, 120.0],
            "rsi_15m": [30.0, 32.0, 35.0],
            "volume_rel": [2.0, 2.2, 2.5],
            "atr_pct": [0.5, 0.55, 0.6],
            "quality_score": [70.0, 72.0, 75.0],
            "rsi_gap_1d": [-10.0, -8.0, -5.0],
            "rsi_1h": [28.0, 30.0, 32.0],
            "future_max_gain_pct": [2.0, 1.5, 1.0],
            "future_min_drawdown_pct": [0.5, 0.3, 0.2],
            "future_bars_to_peak": [10, 8, 5],
        })
        
        feed = ReplayDataFeed.from_dataframe_full_replay("BTCUSDT", "15m", fake_df)
        
        assert feed.total_bars == 3
        assert feed.has_next()
    
    def test_from_dataframe_snapshot_has_expected_keys(self):
        """Test snapshot dict has expected keys for SilverAnalyzer."""
        fake_df = pd.DataFrame({
            "ts": ["2023-01-01 00:00:00"],
            "open": [42000.0],
            "high": [42100.0],
            "low": [41900.0],
            "close": [42050.0],
            "volume": [100.0],
            "rsi_15m": [30.0],
            "volume_rel": [2.0],
            "atr_pct": [0.5],
            "quality_score": [70.0],
            "rsi_gap_1d": [-10.0],
            "rsi_1h": [28.0],
            "future_max_gain_pct": [2.0],
            "future_min_drawdown_pct": [0.5],
            "future_bars_to_peak": [10],
        })
        
        feed = ReplayDataFeed.from_dataframe_full_replay("BTCUSDT", "15m", fake_df)
        snapshot = feed.next()
        
        # Check required keys
        assert "symbol" in snapshot
        assert snapshot["symbol"] == "BTCUSDT"
        assert "rsi_15m" in snapshot
        assert snapshot["rsi_15m"] == 30.0
        assert "volume_rel" in snapshot
        assert "atr_pct" in snapshot
        assert "quality_score" in snapshot
        assert "future_max_gain_pct" in snapshot
        assert snapshot["future_max_gain_pct"] == 2.0
    
    def test_from_dataframe_iteration(self):
        """Test iterating through all bars in feed."""
        fake_df = pd.DataFrame({
            "ts": ["2023-01-01 00:00:00", "2023-01-01 00:15:00", "2023-01-01 00:30:00"],
            "open": [42000.0, 42100.0, 42200.0],
            "high": [42100.0, 42200.0, 42300.0],
            "low": [41900.0, 42000.0, 42100.0],
            "close": [42050.0, 42150.0, 42250.0],
            "volume": [100.0, 110.0, 120.0],
            "rsi_15m": [30.0, 32.0, 35.0],
            "volume_rel": [2.0, 2.2, 2.5],
            "atr_pct": [0.5, 0.55, 0.6],
        })
        
        feed = ReplayDataFeed.from_dataframe_full_replay("BTCUSDT", "15m", fake_df)
        
        # Iterate through all bars
        bar_count = 0
        while feed.has_next():
            snapshot = feed.next()
            bar_count += 1
            assert snapshot is not None
        
        assert bar_count == 3
        assert not feed.has_next()
        assert feed.next() is None


class TestFullReplayRunner:
    """Tests for run_silver_15m_full_replay_for_symbol function."""
    
    def test_file_not_found_raises_error(self):
        """Test that missing dataset raises FileNotFoundError."""
        from tezaver.matrix.wargame.runner import run_silver_15m_full_replay_for_symbol
        
        with pytest.raises(FileNotFoundError):
            run_silver_15m_full_replay_for_symbol(
                symbol="NONEXISTENT_SYMBOL",
                risk=0.01,
                mode="contract",
                tightness=50,
            )
    
    # TODO: Add smoke test with real data once full_replay_bars_v1.parquet is created
    # def test_smoke_run_btc(self):
    #     """Smoke test with BTCUSDT full replay."""
    #     from tezaver.matrix.wargame.runner import run_silver_15m_full_replay_for_symbol
    #     
    #     report = run_silver_15m_full_replay_for_symbol(
    #         symbol="BTCUSDT",
    #         risk=0.01,
    #         mode="contract",
    #         tightness=0,
    #     )
    #     
    #     assert report.capital_start == 100.0
    #     assert report.capital_end >= 0.0
    #     assert report.trade_count >= 0
    #     assert len(report.equity_curve) > 0
