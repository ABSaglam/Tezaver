import os
import json
import pytest
from http.client import HTTPConnection
import threading
import time

def test_panel_build_debug(tmp_path):
    """Test /_debug/build endpoint returns expected keys."""
    home = str(tmp_path)
    
    # Import and configure
    from tezaver.matrix.apps import panel_server
    
    # Set home
    panel_server._PANEL_HOME = home
    panel_server.PanelHandler.home = home
    
    # Start server in thread
    from http.server import HTTPServer
    server = HTTPServer(('', 18085), panel_server.PanelHandler)
    
    thread = threading.Thread(target=lambda: server.handle_request())
    thread.start()
    
    time.sleep(0.1)  # Give server time to start
    
    # Make request
    conn = HTTPConnection('localhost', 18085, timeout=5)
    conn.request('GET', '/_debug/build')
    resp = conn.getresponse()
    
    assert resp.status == 200
    
    data = json.loads(resp.read().decode())
    
    # Check required keys
    assert "commit" in data
    assert "branch" in data
    assert "home" in data
    assert "panel_file" in data
    assert "counts" in data
    
    # Check home matches tmp_path
    assert data["home"] == os.path.abspath(home)
    
    conn.close()
    thread.join(timeout=1)
