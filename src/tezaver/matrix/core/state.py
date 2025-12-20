from dataclasses import dataclass, field
from typing import List

@dataclass
class PositionState:
    qty: float = 0.0
    entry_price: float = 0.0

@dataclass
class StrategyState:
    last_decision: str = "HOLD"
    last_bar_ts: int = 0

@dataclass
class RunState:
    position: PositionState = field(default_factory=PositionState)
    strategy: StrategyState = field(default_factory=StrategyState)

def validate_state(state: RunState) -> List[str]:
    """Checks state invariants."""
    errors = []
    
    if state.position.qty < 0:
        errors.append(f"Negative position qty: {state.position.qty}")
    if state.position.entry_price < 0:
        errors.append(f"Negative entry price: {state.position.entry_price}")
    
    if state.strategy.last_bar_ts < 0:
        errors.append(f"Negative last_bar_ts: {state.strategy.last_bar_ts}")
        
    return errors
