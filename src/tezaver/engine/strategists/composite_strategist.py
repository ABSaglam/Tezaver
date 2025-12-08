"""
Tezaver Composite Strategist (The General) - M25
================================================

This module implements a strategist that combines multiple sub-strategists.
It allows the system to evaluate multiple strategies simultaneously (e.g., Rally, Dip Buy, Breakout).
"""

from typing import List, Optional, Dict, Any
from tezaver.engine.interfaces import IStrategist, MarketSignal, TradeDecision

class CompositeStrategist(IStrategist):
    def __init__(self, strategies: List[IStrategist] = None):
        """
        Args:
            strategies: A list of IStrategist instances.
        """
        self.strategies = strategies or []
        
    def add_strategy(self, strategy: IStrategist):
        self.strategies.append(strategy)
        
    def evaluate(self, signal: MarketSignal, account_state: Dict[str, float]) -> Optional[TradeDecision]:
        """
        Ask all sub-strategists for a decision.
        Returns the first positive decision (Priority logic can be enhanced later).
        """
        # Simple Priority: First strategy in list that says "YES" wins.
        for strategy in self.strategies:
            decision = strategy.evaluate(signal, account_state)
            if decision:
                # Enrich reason
                decision.reason = f"[{type(strategy).__name__}] {decision.reason}"
                return decision
                
        return None
