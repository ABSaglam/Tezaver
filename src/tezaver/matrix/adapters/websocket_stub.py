from typing import Optional, List
import time

class WebSocketStub:
    """
    Stub for testing. Replays a list of messages then returns None (or disconnects).
    """
    def __init__(self, messages: List[str] = None):
        self.messages = messages or []
        self.connected = False
        self.cursor = 0
        
    def connect(self, url: str) -> None:
        self.connected = True
        self.url = url
        
    def recv(self, timeout: float = 1.0) -> Optional[str]:
        if not self.connected:
            raise ConnectionError("Not connected")
            
        if self.cursor < len(self.messages):
            msg = self.messages[self.cursor]
            self.cursor += 1
            return msg
        
        # Simulate silence
        time.sleep(0.1)
        return None
        
    def close(self) -> None:
        self.connected = False
