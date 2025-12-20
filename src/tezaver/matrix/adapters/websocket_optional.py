from typing import Optional
import sys

# Optional dependency
try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

class WebSocketOptional:
    """
    Real WebSocket implementation using `websocket-client`.
    """
    def __init__(self):
        self.ws = None
        if not HAS_WEBSOCKET:
            print("WARNING: 'websocket-client' lib not installed. Runner will fail if used.", file=sys.stderr)
            
    def connect(self, url: str) -> None:
        if not HAS_WEBSOCKET: raise ImportError("No websocket-client lib")
        # create_connection handles handshake
        self.ws = websocket.create_connection(url, timeout=5)
        
    def recv(self, timeout: float = 1.0) -> Optional[str]:
        if not self.ws: raise ConnectionError("Not connected")
        self.ws.settimeout(timeout)
        try:
            return self.ws.recv()
        except websocket.WebSocketTimeoutException:
            return None
        except Exception as e:
            # Let runner handle disconnects
            raise e
            
    def close(self) -> None:
        if self.ws:
            self.ws.close()
            self.ws = None
