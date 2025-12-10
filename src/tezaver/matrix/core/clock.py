# Matrix V2 Clock Module
"""
Clock protocol for Matrix v2 time management.
"""

from datetime import datetime
from typing import Protocol


class IClock(Protocol):
    """
    Protocol for time management.
    
    Implementations provide current time from various sources:
    - Live: System clock
    - Replay: Simulated time from historical data
    """
    
    def now(self) -> datetime:
        """
        Get the current time.
        
        Returns:
            Current datetime (real or simulated).
        """
        ...
