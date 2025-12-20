"""
Live Cluster - V4 Compatible Shim

Provides LiveCluster and build_live_cluster_from_profile_board for UI.
"""

from dataclasses import dataclass
from typing import List, Optional

@dataclass  
class LiveCell:
    """Represents a live trading cell."""
    symbol: str
    timeframe: str
    profile_id: str
    
@dataclass
class LiveCluster:
    """Cluster of live trading cells."""
    cells: List[LiveCell]
    initial_capital: float
    risk_mode: str
    
    def list_cells(self) -> List[LiveCell]:
        return self.cells
        
    def get_equity(self, symbol: str, timeframe: str, profile_id: str) -> float:
        if not self.cells:
            return 0.0
        return self.initial_capital / len(self.cells)

def build_live_cluster_from_profile_board(
    initial_capital: float = 10000.0,
    risk_mode: str = "conservative",
) -> LiveCluster:
    """
    Build a live cluster from the profile board.
    """
    from tezaver.matrix.profile_board import build_profile_board
    
    rows = build_profile_board()
    
    cells = []
    for r in rows:
        if r.live_eligible:
            cells.append(LiveCell(
                symbol=r.symbol,
                timeframe=r.timeframe,
                profile_id=r.profile_id,
            ))
            
    return LiveCluster(
        cells=cells,
        initial_capital=initial_capital,
        risk_mode=risk_mode,
    )
