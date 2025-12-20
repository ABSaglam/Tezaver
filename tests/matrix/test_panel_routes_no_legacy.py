import os
import json
import pytest
from http.client import HTTPConnection
import threading
import time

def test_panel_routes_no_legacy(tmp_path):
    """Test V4 panel has no legacy routes and shows empty state."""
    home = str(tmp_path)
    
    # Import and configure
    from tezaver.matrix.apps import panel_server
    
    # Set home
    panel_server._PANEL_HOME = home
    panel_server.PanelHandler.home = home
    
    # Start server in thread
    from http.server import HTTPServer
    server = HTTPServer(('', 18086), panel_server.PanelHandler)
    
    def handle_requests():
        for _ in range(3):  # Handle 3 requests
            server.handle_request()
    
    thread = threading.Thread(target=handle_requests)
    thread.start()
    
    time.sleep(0.1)
    
    # Test 1: /_debug/build returns 200
    conn = HTTPConnection('localhost', 18086, timeout=5)
    conn.request('GET', '/_debug/build')
    resp = conn.getresponse()
    assert resp.status == 200
    data = json.loads(resp.read().decode())
    assert "commit" in data
    conn.close()
    
    # Test 2: / returns 200 with "Sistem Boş" (empty state)
    conn = HTTPConnection('localhost', 18086, timeout=5)
    conn.request('GET', '/')
    resp = conn.getresponse()
    assert resp.status == 200
    body = resp.read().decode()
    assert "Sistem Boş" in body
    assert "Build:" in body
    assert "Home:" in body
    conn.close()
    
    # Test 3: /legacy returns 404 (no legacy route)
    conn = HTTPConnection('localhost', 18086, timeout=5)
    conn.request('GET', '/legacy')
    resp = conn.getresponse()
    assert resp.status == 404
    conn.close()
    
    thread.join(timeout=2)
