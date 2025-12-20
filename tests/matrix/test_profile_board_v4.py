import os
import json
import pytest
from tezaver.matrix.profile_board import build_profile_board, ProfileBoardRow

def test_profile_board_empty_home(tmp_path):
    """Test build_profile_board works with empty home directory."""
    home = str(tmp_path)
    
    # Should not crash on empty home
    rows = build_profile_board(home)
    
    assert isinstance(rows, list)
    assert len(rows) == 0  # Empty home = no profiles

def test_profile_board_with_approved(tmp_path):
    """Test build_profile_board reads approved candidates."""
    home = str(tmp_path)
    
    # Create approved directory with a manifest
    approved_dir = tmp_path / "approved" / "TEST_CANDIDATE"
    approved_dir.mkdir(parents=True)
    
    with open(approved_dir / "manifest.json", "w") as f:
        json.dump({
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "pnl_pct": 25.5,
            "trades": 100,
            "max_risk_per_trade": 0.02,
        }, f)
        
    rows = build_profile_board(home)
    
    assert len(rows) == 1
    
    r = rows[0]
    assert r.symbol == "BTCUSDT"
    assert r.timeframe == "15m"
    assert r.profile_id == "TEST_CANDIDATE"
    assert r.status == "APPROVED"
    assert r.pnl_pct == 25.5
    assert r.trades == 100
    assert r.max_risk_per_trade == 0.02
    assert r.live_eligible is True
