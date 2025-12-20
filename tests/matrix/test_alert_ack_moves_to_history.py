import os
import json
import pytest
from tezaver.matrix.adapters.notifier_file import FileNotifier

def test_alert_ack_moves_to_history(tmp_path):
    home = str(tmp_path)
    notifier = FileNotifier(home)
    
    alert = {"alert_id": "A1", "ts": 100, "message": "Test"}
    notifier.emit_alert(alert)
    
    # Verify Active
    assert len(notifier.list_active()) == 1
    assert os.path.exists(tmp_path / "alerts" / "active" / "A1.json")
    
    # Ack
    notifier.ack("A1")
    
    # Verify History
    assert len(notifier.list_active()) == 0
    assert not os.path.exists(tmp_path / "alerts" / "active" / "A1.json")
    assert os.path.exists(tmp_path / "alerts" / "history" / "A1.json")
