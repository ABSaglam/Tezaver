import pytest
from unittest.mock import MagicMock
from tezaver.matrix.live.restart_reconciler import RestartReconciler
from tezaver.matrix.ports.broker_port import BrokerPort

def test_reconcile_clean_start():
    broker = MagicMock(spec=BrokerPort)
    broker.get_open_orders.return_value = []
    broker.get_positions.return_value = []
    
    reconciler = RestartReconciler()
    report = reconciler.reconcile(broker, "run123", [], [])
    
    assert report.ok is True
    assert report.status == "SUCCESS"
    assert len(report.actions_taken) == 0

def test_reconcile_cancels_unknown_orders():
    broker = MagicMock(spec=BrokerPort)
    # One known, one unknown
    broker.get_open_orders.return_value = [
        {"id": "known_1"},
        {"id": "unknown_1"}
    ]
    broker.get_positions.return_value = []
    
    reconciler = RestartReconciler()
    report = reconciler.reconcile(broker, "run123", ["known_1"], [])
    
    assert len(report.unknown_orders) == 1
    assert report.unknown_orders[0]["id"] == "unknown_1"
    assert "CANCEL_UNKNOWN_ORDER:unknown_1" in report.actions_taken
    broker.cancel_order.assert_called_with("unknown_1")

def test_reconcile_orphan_position_safe_mode():
    broker = MagicMock(spec=BrokerPort)
    broker.get_open_orders.return_value = []
    # Orphan position in ETHUSDT
    broker.get_positions.return_value = [
        {"symbol": "ETHUSDT", "qty": 1.0}
    ]
    
    # We only expect BTCUSDT
    reconciler = RestartReconciler(policy={"flatten_orphans": "safe_mode", "cancel_unknown": True})
    report = reconciler.reconcile(broker, "run123", [], ["BTCUSDT"])
    
    assert len(report.orphan_positions) == 1
    assert report.ok is False # safe_mode policy forces failure
    assert report.status == "INCONSISTENT"
