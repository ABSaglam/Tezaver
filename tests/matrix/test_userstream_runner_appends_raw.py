import pytest
from unittest.mock import MagicMock
from tezaver.matrix.core.userstream_runner import UserStreamRunner
from tezaver.matrix.core.userstream_manager import UserStreamManager
from tezaver.matrix.ports.websocket_port import WebSocketPort
from tezaver.matrix.adapters.websocket_stub import WebSocketStub

def test_userstream_runner_appends_raw(tmp_path):
    home = str(tmp_path)
    mgr = MagicMock(spec=UserStreamManager)
    
    # Stub Messages
    msgs = ['{"id": 1}', '{"id": 2}', '{"id": 3}']
    ws = WebSocketStub(msgs)
    ws.connect("wss://dummy") # Ensure it doesn't raise ConnectionError
    
    # Runner
    runner = UserStreamRunner(ws, mgr, home)
    
    # Setup Manager Status mock
    mgr.get_status.return_value = {"status": "CONNECTED_WS", "listenKey": "LKEY"}
    
    # Run 5 ticks (3 msgs + 2 empty)
    runner.run(ticks=5)
    
    # Verify Manager calls
    assert mgr.append_raw_message.call_count == 3
    # Check connect call
    assert ws.connected
