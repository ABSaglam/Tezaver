import os
import json
import pytest
from unittest.mock import patch, MagicMock
from tezaver.matrix.core.cloud_loop import CloudLoopSupervisor

def test_cloud_loop_respects_global_pause_behavior(tmp_path):
    # This test verifies loop continues running, but Runtime logic handles PAUSE inside its tick.
    # The Supervisor does NOT stop looping on pause, it just calls Runtime which should be no-op.
    # We verify that LOOP_RUNTIME_OK is emitted but Runtime likely signals "paused" or 0 processed.
    # Actually Supervisor doesn't inspect return of runtime yet.
    # But we can check event log.
    
    home = str(tmp_path)
    
    # Set Global Paused
    os.makedirs(tmp_path / "cloud_runtime", exist_ok=True)
    with open(tmp_path / "cloud_runtime" / "global_risk.json", "w") as f:
        json.dump({"paused": True}, f)
        
    with patch("tezaver.matrix.core.secrets.load_binance_secrets", return_value={"present":True}), \
         patch("tezaver.matrix.core.cloud_loop.WebSocketOptional"):
         
         sup = CloudLoopSupervisor(home)
         # Mock cloud_runtime_tick to verify it was called
         with patch("tezaver.matrix.core.cloud_loop.cloud_runtime_tick") as mock_tick:
             sup.run_loop(ticks=1, steps=1, userstream_recv=1, hours=24)
             
             assert mock_tick.called
             
             # Check History
             with open(sup.history_path) as f: log = f.read()
             assert "LOOP_RUNTIME_OK" in log
             
             # Real validation: Runtime itself (which we mock here) would check paused.
             # This test confirms Loop doesn't crash or abort on Pause.
             # Loop runs.
             assert sup.state["tick_count"] == 1
