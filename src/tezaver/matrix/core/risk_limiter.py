"""
MX-2011: Global Risk Limiter for WAR Mode
Limits: MAX_TOTAL_NOTIONAL, MAX_CONCURRENT_POSITIONS, MAX_NOTIONAL_PER_SYMBOL
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_total_notional: float = 100000.0  # Max total position value
    max_concurrent_positions: int = 5      # Max open positions at once
    max_notional_per_symbol: float = 20000.0  # Max per symbol


@dataclass
class PositionState:
    """Tracks current position state."""
    symbol: str
    notional: float
    entry_ts: int
    candidate_id: str


class RiskLimiter:
    """
    MX-2011: Global Risk Limiter
    Enforces limits across all positions in WAR mode.
    """
    
    def __init__(self, limits: RiskLimits = None):
        self.limits = limits or RiskLimits()
        self.positions: Dict[str, PositionState] = {}  # symbol -> position
        self.block_count = 0
        self.block_log: List[Dict] = []
    
    def check_order(
        self, 
        symbol: str, 
        notional: float, 
        candidate_id: str,
        ts: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if order passes risk limits.
        Returns: (allowed, block_reason)
        """
        # 1. Check max concurrent positions
        if symbol not in self.positions:
            if len(self.positions) >= self.limits.max_concurrent_positions:
                reason = f"MAX_CONCURRENT_POSITIONS ({self.limits.max_concurrent_positions})"
                self._log_block(symbol, notional, candidate_id, ts, reason)
                return False, reason
        
        # 2. Check max notional per symbol
        current_symbol_notional = 0
        if symbol in self.positions:
            current_symbol_notional = self.positions[symbol].notional
        
        if current_symbol_notional + notional > self.limits.max_notional_per_symbol:
            reason = f"MAX_NOTIONAL_PER_SYMBOL ({self.limits.max_notional_per_symbol})"
            self._log_block(symbol, notional, candidate_id, ts, reason)
            return False, reason
        
        # 3. Check max total notional
        total_notional = sum(p.notional for p in self.positions.values())
        if total_notional + notional > self.limits.max_total_notional:
            reason = f"MAX_TOTAL_NOTIONAL ({self.limits.max_total_notional})"
            self._log_block(symbol, notional, candidate_id, ts, reason)
            return False, reason
        
        return True, None
    
    def _log_block(self, symbol: str, notional: float, candidate_id: str, ts: int, reason: str):
        """Log a blocked order."""
        self.block_count += 1
        self.block_log.append({
            "ts": ts,
            "symbol": symbol,
            "notional": notional,
            "candidate_id": candidate_id,
            "reason": reason
        })
    
    def open_position(self, symbol: str, notional: float, candidate_id: str, ts: int):
        """Record a new position."""
        self.positions[symbol] = PositionState(
            symbol=symbol,
            notional=notional,
            entry_ts=ts,
            candidate_id=candidate_id
        )
    
    def close_position(self, symbol: str):
        """Close a position."""
        if symbol in self.positions:
            del self.positions[symbol]
    
    def get_total_notional(self) -> float:
        """Get total notional across all positions."""
        return sum(p.notional for p in self.positions.values())
    
    def get_summary(self) -> Dict:
        """Get risk state summary."""
        return {
            "open_positions": len(self.positions),
            "total_notional": self.get_total_notional(),
            "block_count": self.block_count,
            "limits": {
                "max_total_notional": self.limits.max_total_notional,
                "max_concurrent_positions": self.limits.max_concurrent_positions,
                "max_notional_per_symbol": self.limits.max_notional_per_symbol
            }
        }
