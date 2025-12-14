# Live State Tools Tests
"""
Tests for live_state_tools module.
"""

import json
from pathlib import Path

import pytest


class TestLoadLiveCellState:
    """Tests for load_live_cell_state function."""
    
    def test_missing_file_returns_empty_state(self, tmp_path: Path, monkeypatch):
        """Missing state file should return empty summary."""
        import tezaver.matrix.live.live_state_tools as tools
        monkeypatch.setattr(tools, "STATE_DIR", tmp_path)

        from tezaver.matrix.live.live_state_tools import load_live_cell_state

        summary = load_live_cell_state(
            "BTCUSDT", "15m", "BTC_SILVER_15M_CORE_V1",
            initial_capital=100.0,
        )
        
        assert summary.equity is None
        assert summary.trade_count == 0
        assert summary.pnl_pct is None
    
    def test_existing_file_loads_state(self, tmp_path: Path, monkeypatch):
        """Existing state file should load equity and ledger."""
        import tezaver.matrix.live.live_state_tools as tools
        monkeypatch.setattr(tools, "STATE_DIR", tmp_path)

        # Create state file
        state_file = tmp_path / "BTCUSDT_15m_BTC_SILVER_15M_CORE_V1.json"
        data = {
            "equity": 110.0,
            "ledger": [
                {"side": "OPEN_LONG", "pnl": 5.0, "timestamp": "2025-12-11T12:00:00Z"},
                {"side": "CLOSE", "pnl": 5.0, "timestamp": "2025-12-11T13:00:00Z"},
            ],
        }
        state_file.write_text(json.dumps(data), encoding="utf-8")

        from tezaver.matrix.live.live_state_tools import load_live_cell_state

        summary = load_live_cell_state(
            "BTCUSDT", "15m", "BTC_SILVER_15M_CORE_V1",
            initial_capital=100.0,
        )

        assert summary.equity == 110.0
        assert summary.trade_count == 2
        assert summary.pnl_pct == pytest.approx(10.0)  # (110/100 - 1) * 100
        assert summary.last_side == "CLOSE"
        assert summary.last_pnl == 5.0
        assert summary.last_ts == "2025-12-11T13:00:00Z"
    
    def test_corrupt_file_returns_empty_state(self, tmp_path: Path, monkeypatch):
        """Corrupt state file should return empty summary."""
        import tezaver.matrix.live.live_state_tools as tools
        monkeypatch.setattr(tools, "STATE_DIR", tmp_path)

        # Create corrupt file
        state_file = tmp_path / "ETHUSDT_15m_ETH_SILVER.json"
        state_file.write_text("not valid json {{{", encoding="utf-8")

        from tezaver.matrix.live.live_state_tools import load_live_cell_state

        summary = load_live_cell_state(
            "ETHUSDT", "15m", "ETH_SILVER",
            initial_capital=100.0,
        )

        assert summary.equity is None
        assert summary.trade_count == 0
