"""
Live Loop Service - V4 Compatible Shim

Provides singleton service for live loop control in UI.
"""

from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Any

TICK_POLICY_ON_CLOSED_BAR = "on_closed_bar"
TICK_POLICY_ON_ANY_NEW_BAR = "on_any_new_bar"

@dataclass
class LoopStatus:
    running: bool = False
    polls: int = 0
    ticks: int = 0  
    skips: int = 0
    last_error: Optional[str] = None

class LiveLoopService:
    """Singleton service for live loop control."""
    
    _instance: Optional['LiveLoopService'] = None
    
    def __init__(self):
        self._running = False
        self._polls = 0
        self._ticks = 0
        self._skips = 0
        self._last_error: Optional[str] = None
        self._cells: List[Tuple[str, str]] = []
        
    @classmethod
    def get(cls) -> 'LiveLoopService':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def status(self) -> LoopStatus:
        return LoopStatus(
            running=self._running,
            polls=self._polls,
            ticks=self._ticks,
            skips=self._skips,
            last_error=self._last_error,
        )
        
    def start(
        self,
        cells: List[Tuple[str, str]],
        use_real: bool = False,
        tick_policy: str = TICK_POLICY_ON_CLOSED_BAR,
        poll_interval: float = 5.0,
        max_runtime: float = 3600.0,
    ) -> bool:
        if self._running:
            return False
        self._cells = cells
        self._running = True
        self._last_error = None
        return True
        
    def stop(self) -> bool:
        if not self._running:
            return False
        self._running = False
        return True
        
    def get_cell_metrics(self) -> List[Dict[str, Any]]:
        metrics = []
        for symbol, tf in self._cells:
            metrics.append({
                "symbol": symbol,
                "timeframe": tf,
                "last_closed_bar_ts": None,
                "lag_sec": None,
                "ticks_count": 0,
                "skips_count": 0,
                "last_tick_reason": "N/A",
                "last_close": None,
            })
        return metrics
