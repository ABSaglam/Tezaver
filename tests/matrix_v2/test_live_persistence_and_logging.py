# Live Persistence and Logging Tests
"""
Tests for LiveAccountStore persistence and JsonFileEventSink.
"""

import json
from pathlib import Path

import pytest

from tezaver.matrix.live.live_account_store import LiveAccountStore
from tezaver.matrix.core.telemetry import (
    JsonFileEventSink,
    MatrixEvent,
    MatrixEventType,
)
from tezaver.matrix.core.guardrail import GuardrailEnvironment


class TestLiveAccountStorePersistence:
    """Tests for LiveAccountStore file persistence."""
    
    def test_state_persists_to_disk(self, tmp_path: Path):
        """apply_execution should save state to disk."""
        state_file = tmp_path / "state.json"
        store = LiveAccountStore(
            initial_capital=100.0,
            state_file_path=str(state_file),
        )

        # Initial equity should be 100
        assert store.get_equity() == 100.0

        # Apply execution
        store.apply_execution({
            "pnl": 10.0,
            "equity_before": 100.0,
            "equity_after": 110.0,
        })
        
        assert store.get_equity() == 110.0
        assert state_file.exists()

        # Verify file contents
        with state_file.open("r") as f:
            data = json.load(f)
        assert data["equity"] == 110.0
    
    def test_state_loads_from_disk(self, tmp_path: Path):
        """New store should load existing state from disk."""
        state_file = tmp_path / "state.json"
        
        # Create and populate first store
        store1 = LiveAccountStore(
            initial_capital=100.0,
            state_file_path=str(state_file),
        )
        store1.apply_execution({
            "pnl": 25.0,
            "equity_before": 100.0,
            "equity_after": 125.0,
        })
        
        # Create second store with different initial_capital
        store2 = LiveAccountStore(
            initial_capital=50.0,  # Should be ignored
            state_file_path=str(state_file),
        )
        
        # Should load from disk, not use initial_capital
        assert store2.get_equity() == 125.0
    
    def test_reset_deletes_state_file(self, tmp_path: Path):
        """reset() should delete state file."""
        state_file = tmp_path / "state.json"
        store = LiveAccountStore(
            initial_capital=100.0,
            state_file_path=str(state_file),
        )
        store.apply_execution({
            "pnl": 10.0,
            "equity_before": 100.0,
            "equity_after": 110.0,
        })
        assert state_file.exists()
        
        store.reset()
        assert not state_file.exists()
        assert store.get_equity() == 100.0


class TestJsonFileEventSink:
    """Tests for JsonFileEventSink NDJSON logging."""
    
    def test_writes_event_to_file(self, tmp_path: Path):
        """log() should write event as NDJSON."""
        log_file = tmp_path / "events.ndjson"
        sink = JsonFileEventSink(path=log_file)

        evt = MatrixEvent(
            event_type=MatrixEventType.TICK_START,
            symbol="BTCUSDT",
            timeframe="15m",
            profile_id="BTC_SILVER_15M_CORE_V1",
            environment=GuardrailEnvironment.LIVE,
            tick_index=0,
            details={"note": "test"},
        )
        sink.log(evt)

        assert log_file.exists()
        lines = log_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["symbol"] == "BTCUSDT"
        assert data["details"]["note"] == "test"
    
    def test_appends_multiple_events(self, tmp_path: Path):
        """Multiple log() calls should append to file."""
        log_file = tmp_path / "events.ndjson"
        sink = JsonFileEventSink(path=log_file)

        for i in range(3):
            evt = MatrixEvent(
                event_type=MatrixEventType.INFO,
                symbol="ETHUSDT",
                tick_index=i,
            )
            sink.log(evt)

        lines = log_file.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 3
        assert len(sink) == 3
