# Matrix Operator Console Tests
"""
Tests for Matrix Operator Console v1.
"""

import pytest


class TestOperatorConsole:
    """Tests for operator console functionality."""
    
    def test_build_operator_console_snapshot_returns_profiles(self):
        """build_operator_console_snapshot should return at least 1 profile."""
        from tezaver.matrix.operator_console import build_operator_console_snapshot
        
        snapshot = build_operator_console_snapshot()
        
        assert "board_rows" in snapshot
        assert "summary" in snapshot
        assert "live_cells" in snapshot
        
        assert len(snapshot["board_rows"]) > 0
        assert snapshot["summary"].total_profiles > 0
    
    def test_summary_matches_board_rows(self):
        """Summary counts should match board_rows data."""
        from tezaver.matrix.operator_console import build_operator_console_snapshot
        
        snapshot = build_operator_console_snapshot()
        
        board_rows = snapshot["board_rows"]
        summary = snapshot["summary"]
        
        assert summary.total_profiles == len(board_rows)
        assert summary.live_eligible_count == sum(1 for r in board_rows if r.live_eligible)
    
    def test_live_cells_match_eligible_rows(self):
        """Live cells should match live_eligible=True rows."""
        from tezaver.matrix.operator_console import build_operator_console_snapshot
        
        snapshot = build_operator_console_snapshot()
        
        board_rows = snapshot["board_rows"]
        live_cells = snapshot["live_cells"]
        
        # Get eligible rows
        eligible_keys = {
            (r.symbol, r.timeframe, r.profile_id)
            for r in board_rows if r.live_eligible
        }
        
        # Get live cell keys
        live_keys = {
            (c.symbol, c.timeframe, c.profile_id)
            for c in live_cells
        }
        
        # Should match
        assert eligible_keys == live_keys
    
    def test_main_runs_without_error(self, capsys):
        """main() should run without error."""
        from tezaver.matrix.operator_console import main
        
        # Should not raise
        main(argv=None)
        
        captured = capsys.readouterr()
        assert "Matrix Operator Console v1" in captured.out
    
    def test_main_with_custom_args(self, capsys):
        """main() should accept custom arguments."""
        from tezaver.matrix.operator_console import main
        
        main(argv=["200.0", "experiment"])
        
        captured = capsys.readouterr()
        assert "initial_capital=200.0" in captured.out
        assert "mode=experiment" in captured.out
