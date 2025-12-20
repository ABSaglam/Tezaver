import pytest
from unittest.mock import MagicMock
from tezaver.matrix.core.userstream_manager import UserStreamManager
from tezaver.matrix.adapters.binance_rest_client import BinanceRestClient

def test_userstream_listenkey_lifecycle_calls(tmp_path):
    client = MagicMock(spec=BinanceRestClient)
    home = str(tmp_path)
    mgr = UserStreamManager(client, home)
    
    # 1. Start
    client._request.return_value = {"listenKey": "LK_123"}
    key = mgr.start_stream()
    
    assert key == "LK_123"
    client._request.assert_called_with("POST", "/fapi/v1/listenKey", signed=False, params={})
    
    status = mgr.get_status()
    assert status["status"] == "CONNECTED"
    assert status["listenKey"] == "LK_123"
    
    # 2. Keepalive
    mgr.keepalive()
    client._request.assert_called_with("PUT", "/fapi/v1/listenKey", signed=False, params={})
    
    # 3. Close
    mgr.close()
    client._request.assert_called_with("DELETE", "/fapi/v1/listenKey", signed=False, params={})
    
    status_closed = mgr.get_status()
    assert status_closed["status"] == "CLOSED"
