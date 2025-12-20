import os
import json
import pytest
from unittest.mock import MagicMock, patch
from tezaver.matrix.core.cloud_loop import CloudLoopSupervisor

def test_cloud_loop_happy_path(tmp_path):
    home = str(tmp_path)
    
    # Needs to be careful with patching.
    # We patch the imported names in cloud_loop module.
    
    with patch("tezaver.matrix.core.cloud_loop.load_binance_secrets", return_value={"api_key": "k", "api_secret": "s", "present": True}), \
         patch("tezaver.matrix.core.cloud_loop.WebSocketOptional"), \
         patch("tezaver.matrix.core.cloud_loop.UserStreamManager") as mock_mgr_cls, \
         patch("tezaver.matrix.core.cloud_loop.BinanceRestClient") as mock_client_cls, \
         patch("tezaver.matrix.core.cloud_loop.UserStreamRunner") as mock_runner_cls:
         
         mock_mgr = mock_mgr_cls.return_value
         mock_runner = mock_runner_cls.return_value
         
         sup = CloudLoopSupervisor(home)
         res = sup.run_loop(ticks=2, steps=1, userstream_recv=1, hours=24)
            
         # Assert ticks processed (even if error, loop continues)
         assert res["ticks_processed"] == 2
            
         # Check History for Errors
         with open(sup.history_path) as f: lines = f.readlines()
         content = "".join(lines)
         
         if "LOOP_TICK_FAIL" in content:
             print("DEBUG FAILURES:\n", content)
             
         # Expect NO failures in happy path
         assert "LOOP_TICK_FAIL" not in content
         assert "LOOP_RUNTIME_OK" in content
         
         # Check State
         with open(sup.state_path) as f: state = json.load(f)
         assert state["tick_count"] == 2
