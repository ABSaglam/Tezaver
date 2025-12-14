# Matrix Profile Board Tests
"""
Tests for Matrix Strategy Board v1.
"""

import pytest
from pathlib import Path


class TestProfileBoard:
    """Tests for profile board functionality."""
    
    def test_profile_board_builds_rows_for_silver_15m(self):
        """build_profile_board should return rows for all Silver 15m profiles."""
        from tezaver.matrix.profile_board import build_profile_board
        
        rows = build_profile_board()
        
        # Should have at least some rows
        assert len(rows) > 0
        
        # Check that expected profiles exist
        profile_keys = {(r.symbol, r.timeframe, r.profile_id) for r in rows}
        
        # BTC should be present
        assert ("BTCUSDT", "15m", "BTC_SILVER_15M_CORE_V1") in profile_keys
        
        # ETH should be present
        assert ("ETHUSDT", "15m", "ETH_SILVER_15M_CORE_V1") in profile_keys
        
        # SOL should be present
        assert ("SOLUSDT", "15m", "SOL_SILVER_15M_CORE_V1") in profile_keys
    
    def test_btc_profile_is_live_eligible(self):
        """BTC APPROVED profile with risk contract should be live eligible."""
        from tezaver.matrix.profile_board import build_profile_board
        
        rows = build_profile_board()
        
        btc_row = next(
            (r for r in rows if r.symbol == "BTCUSDT" and r.profile_id == "BTC_SILVER_15M_CORE_V1"),
            None
        )
        
        assert btc_row is not None
        assert btc_row.status.upper() == "APPROVED"
        assert btc_row.max_risk_per_trade is not None
        assert btc_row.live_eligible is True
    
    def test_sol_profile_is_not_live_eligible(self):
        """SOL EXPERIMENTAL profile should not be live eligible."""
        from tezaver.matrix.profile_board import build_profile_board
        
        rows = build_profile_board()
        
        sol_row = next(
            (r for r in rows if r.symbol == "SOLUSDT" and r.profile_id == "SOL_SILVER_15M_CORE_V1"),
            None
        )
        
        assert sol_row is not None
        assert sol_row.status.upper() == "EXPERIMENTAL"
        assert sol_row.live_eligible is False
    
    def test_is_live_eligible_logic(self):
        """_is_live_eligible should follow v1 rules."""
        from tezaver.matrix.profile_board import _is_live_eligible
        
        # APPROVED + risk = eligible
        assert _is_live_eligible("APPROVED", 0.01) is True
        
        # APPROVED + no risk = not eligible
        assert _is_live_eligible("APPROVED", None) is False
        
        # EXPERIMENTAL + risk = not eligible
        assert _is_live_eligible("EXPERIMENTAL", 0.01) is False
        
        # DISABLED + risk = not eligible
        assert _is_live_eligible("DISABLED", 0.01) is False
    
    def test_print_profile_board_runs(self, capsys):
        """print_profile_board should print header."""
        from tezaver.matrix.profile_board import print_profile_board, ProfileBoardRow
        
        rows = [
            ProfileBoardRow(
                symbol="TESTUSDT",
                timeframe="15m",
                profile_id="TEST_PROFILE",
                status="APPROVED",
                pnl_pct=1.5,
                trades=10,
                max_risk_per_trade=0.01,
                live_eligible=True,
            )
        ]
        
        print_profile_board(rows)
        
        captured = capsys.readouterr()
        assert "Matrix Strategy Board v1" in captured.out
        assert "TESTUSDT" in captured.out
        assert "YES" in captured.out
