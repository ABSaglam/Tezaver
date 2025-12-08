"""
Tests for Time-Labs UI Integration logic.
Focuses on data loading, summary building, and basic rendering safety.
"""

import pytest
import pandas as pd
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

from tezaver.ui.explanation_cards import CoinExplanationContext, build_time_labs_summary_tr, load_coin_explanation_context
from tezaver.ui.time_labs_tab import load_time_labs_rallies, load_time_labs_summary

# Mock streamlit to avoid runtime errors during import/execution
import sys
if 'streamlit' not in sys.modules:
    sys.modules['streamlit'] = MagicMock()


class TestTimeLabsUI:
    
    @pytest.fixture
    def mock_context(self):
        ctx = CoinExplanationContext(symbol="BTCUSDT")
        
        ctx.fast15_summary = {
            "meta": {"total_events": 10},
            "summary_tr": "Fast15 Rallisi mevcut."
        }
        
        ctx.time_labs_1h = {
            "meta": {"total_events": 5},
            "summary_tr": "1 Saatlik analizde 5 olay tespit edildi."
        }
        
        ctx.time_labs_4h = {
            "meta": {"total_events": 0},
            "summary_tr": "Olay yok."
        }
        
        return ctx

    def test_build_time_labs_summary_tr(self, mock_context):
        """Verify the Turkish summary builder combines all parts correctly."""
        summary = build_time_labs_summary_tr(mock_context)
        
        assert "⚡️ 15dk Hızlı Yükselişler" in summary
        assert "Fast15 Rallisi mevcut" in summary
        
        assert "🕐 1 Saat Time-Labs" in summary
        assert "1 Saatlik analizde 5 olay tespit edildi" in summary
        
        # 4h has 0 events, should not show up (or show minimal if configured, but logic says pass)
        # Actually logic says: if count > 0 append summary.
        assert "🕓 4 Saat Time-Labs" not in summary

    def test_build_time_labs_summary_empty(self):
        """Verify empty context returns None."""
        ctx = CoinExplanationContext(symbol="EMPTY")
        summary = build_time_labs_summary_tr(ctx)
        assert summary is None

    @patch("tezaver.core.coin_cell_paths.get_time_labs_rallies_path")
    @patch("pandas.read_parquet")
    def test_load_time_labs_rallies(self, mock_read, mock_path_func):
        """Test loading parquet events."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_func.return_value = mock_path
        
        mock_df = pd.DataFrame({"event_time": [100, 200]})
        mock_read.return_value = mock_df
        
        df = load_time_labs_rallies("BTCUSDT", "1h")
        
        assert df is not None
        assert len(df) == 2
        mock_path_func.assert_called_with("BTCUSDT", "1h")

    @patch("tezaver.core.coin_cell_paths.get_time_labs_rallies_summary_path")
    def test_load_time_labs_summary(self, mock_path_func):
        """Test loading JSON summary."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path_func.return_value = mock_path
        
        mock_data = {"summary_tr": "Test Summary"}
        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value.read.return_value = json.dumps(mock_data)
            # Need to mock json.load specifically if read isn't enough, but usually mocking open context manager is tricky
            # Easier to mock json.load directly
            with patch("json.load", return_value=mock_data):
                data = load_time_labs_summary("BTCUSDT", "4h")
                
        assert data["summary_tr"] == "Test Summary"
        mock_path_func.assert_called_with("BTCUSDT", "4h")

    @patch("tezaver.ui.explanation_cards.get_coin_profile_dir")
    def test_load_context_integrates_timelabs(self, mock_dir_func):
        """Test that load_coin_explanation_context attempts to load Time-Labs files."""
        mock_path = MagicMock()
        mock_dir_func.return_value = mock_path
        
        # Setup file exists mocks
        # We need to distinguish between files.
        # This is complex with Path mocks. 
        # Simplified: valid path objects for 1h/4h
        
        path_1h = MagicMock()
        path_1h.exists.return_value = True
        
        path_4h = MagicMock()
        path_4h.exists.return_value = False
        
        # When profile_dir / "filename" is called
        def div_side_effect(arg):
            if "time_labs_1h" in arg:
                return path_1h
            if "time_labs_4h" in arg:
                return path_4h
            return MagicMock(exists=lambda: False)
            
        mock_path.__truediv__.side_effect = div_side_effect
        
        with patch("builtins.open"), patch("json.load") as mock_json_load:
            mock_json_load.return_value = {"data": "ok"}
            
            ctx = load_coin_explanation_context("BTCUSDT")
            
            assert ctx.time_labs_1h == {"data": "ok"}
            assert ctx.time_labs_4h is None
