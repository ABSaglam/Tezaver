import pytest
from unittest.mock import MagicMock, patch
from tezaver.bulut.services.state_reducer import StateReducer
from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.services.persistence_sqlite import SqlitePersistence
from tezaver.bulut.services.telemetry_ndjson import NdjsonTelemetry

@pytest.fixture
def mock_deps():
    config = BulutConfig()
    persistence = MagicMock(spec=SqlitePersistence)
    telemetry = MagicMock(spec=NdjsonTelemetry)
    return config, persistence, telemetry

def test_apply_order_dedup(mock_deps):
    config, persistence, telemetry = mock_deps
    reducer = StateReducer(config, persistence, telemetry)
    
    # Mock persistence.try_mark_event_applied to success then fail
    persistence.try_mark_event_applied.side_effect = [True, False]
    
    event = {
        "i": "123", "s": "BTCUSDT", "T": 1000, "X": "FILLED", "x": "TRADE",
        "z": "0.1", "ap": "50000.0"
    }
    
    # First time -> Applied
    res1 = reducer.apply_order_update(event, "WS")
    assert res1 is True
    persistence.upsert_trade_audit_event.assert_called_once()
    
    # Second time -> Duplicate
    res2 = reducer.apply_order_update(event, "WS")
    assert res2 is False
    # Should not call upsert again
    assert persistence.upsert_trade_audit_event.call_count == 1
    assert reducer._duplicates_count == 1

def test_apply_account_ooo(mock_deps):
    # This logic depends on persistence checking timestamp inside upsert/mark
    # StateReducer delegates OOO check to persistence layer call args.
    # So we just verify StateReducer injects the timestamp correctly.
    
    config, persistence, telemetry = mock_deps
    reducer = StateReducer(config, persistence, telemetry)
    
    event_ts = 2000
    event = {
        "_E": event_ts,
        "P": [
            {"s": "BTCUSDT", "pa": "0.1", "ep": "50000"}
        ]
    }
    
    reducer.apply_account_update(event, "WS")
    
    # Verify persistence call has last_update_ts_ms
    persistence.upsert_position_open.assert_called_once()
    call_kwargs = persistence.upsert_position_open.call_args.kwargs
    assert call_kwargs["last_update_ts_ms"] == event_ts
