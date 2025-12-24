from typing import List
from tezaver.matrix.game.game_models_v1 import GameStep

class GameMetricsV1:
    @staticmethod
    def calculate_max_drawdown(steps: List[GameStep], initial_capital: float) -> float:
        """
        Calculates Max Drawdown % from equity curve.
        """
        if not steps:
            return 0.0
            
        peak = initial_capital
        max_dd = 0.0
        
        for s in steps:
            equity = s.equity_after
            if equity > peak:
                peak = equity
            
            dd = (peak - equity) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
                
        return max_dd * 100.0
