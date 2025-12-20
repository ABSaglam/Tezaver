from typing import Protocol, Optional

class WebSocketPort(Protocol):
    def connect(self, url: str) -> None:
        """Establishes connection."""
        ...

    def recv(self, timeout: float = 1.0) -> Optional[str]:
        """Receives a message string. Returns None if timeout or empty."""
        ...
    
    def close(self) -> None:
        """Closes connection."""
        ...
