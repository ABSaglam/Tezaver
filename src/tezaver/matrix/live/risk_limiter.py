"""
Global Risk Limiter for Matrix Live.

Provides multi-cell notional and position tracking to prevent
over-exposure across symbols/profiles.

Risk unit: NOTIONAL_USDT = abs(qty) * last_price
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class RiskDecisionType(Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"
    CLAMP = "CLAMP"


@dataclass
class RiskLimits:
    """Risk limit configuration."""
    max_total_notional_usdt: float = 500.0
    max_cell_notional_usdt: float = 300.0
    max_open_positions: int = 3
    enforce: str = "BLOCK"  # WARN / BLOCK


@dataclass
class RiskSnapshot:
    """Current risk state snapshot."""
    total_notional_usdt: float = 0.0
    open_positions_count: int = 0
    cells: Dict[str, float] = field(default_factory=dict)  # cell_id -> notional
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_notional_usdt": round(self.total_notional_usdt, 2),
            "open_positions_count": self.open_positions_count,
            "cells": {k: round(v, 2) for k, v in self.cells.items()},
        }


@dataclass
class RiskDecision:
    """Result of risk limit evaluation."""
    allow: bool
    decision: RiskDecisionType
    cell_id: str
    cell_notional: float
    total_notional: float
    open_positions_count: int
    violations: List[str] = field(default_factory=list)
    reason: str = ""
    
    # Limits for telemetry
    max_total_notional: float = 0.0
    max_cell_notional: float = 0.0
    max_open_positions: int = 0
    enforce_mode: str = "BLOCK"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow": self.allow,
            "decision": self.decision.value,
            "cell_id": self.cell_id,
            "cell_notional": round(self.cell_notional, 2),
            "total_notional": round(self.total_notional, 2),
            "open_positions_count": self.open_positions_count,
            "violations": self.violations,
            "reason": self.reason,
            "max_total_notional": round(self.max_total_notional, 2),
            "max_cell_notional": round(self.max_cell_notional, 2),
            "max_open_positions": self.max_open_positions,
            "enforce_mode": self.enforce_mode,
        }


class GlobalRiskLimiter:
    """
    Multi-cell risk limiter.
    
    Tracks open positions and notional across cells,
    evaluates new order requests against limits.
    """
    
    def __init__(
        self,
        limits: Optional[RiskLimits] = None,
        event_sink: Optional[Callable] = None,
    ):
        self._limits = limits or RiskLimits()
        self._event_sink = event_sink
        
        # Track open positions: cell_id -> notional_usdt
        self._open_positions: Dict[str, float] = {}
        
        # Last decision for UI
        self._last_decision: Optional[RiskDecision] = None
    
    @property
    def limits(self) -> RiskLimits:
        return self._limits
    
    @property
    def last_decision(self) -> Optional[RiskDecision]:
        return self._last_decision
    
    def compute_cell_notional(self, qty: float, price: float) -> float:
        """Compute notional USDT for a position."""
        return abs(qty) * price
    
    def compute_totals(self) -> RiskSnapshot:
        """Compute current risk snapshot."""
        total = sum(self._open_positions.values())
        count = len(self._open_positions)
        return RiskSnapshot(
            total_notional_usdt=total,
            open_positions_count=count,
            cells=dict(self._open_positions),
        )
    
    def register_position(self, cell_id: str, notional: float) -> None:
        """Register an open position."""
        if notional > 0:
            self._open_positions[cell_id] = notional
        elif cell_id in self._open_positions:
            del self._open_positions[cell_id]
    
    def unregister_position(self, cell_id: str) -> None:
        """Remove a closed position."""
        if cell_id in self._open_positions:
            del self._open_positions[cell_id]
    
    def evaluate_new_order(
        self,
        cell_id: str,
        req_qty: float,
        price: float,
        context: Optional[Dict[str, Any]] = None,
    ) -> RiskDecision:
        """
        Evaluate if a new order request should be allowed.
        
        Returns RiskDecision with allow/decision/violations.
        """
        ctx = context or {}
        
        # Compute request notional
        req_notional = self.compute_cell_notional(req_qty, price)
        
        # Current snapshot (excluding this cell if already open)
        current_total = sum(
            n for cid, n in self._open_positions.items() 
            if cid != cell_id
        )
        current_count = len([
            cid for cid in self._open_positions 
            if cid != cell_id
        ])
        
        # What-if analysis
        new_total = current_total + req_notional
        new_count = current_count + 1
        
        violations = []
        
        # Check limits
        if new_total > self._limits.max_total_notional_usdt:
            violations.append(
                f"total_notional({new_total:.2f}) > max({self._limits.max_total_notional_usdt:.2f})"
            )
        
        if req_notional > self._limits.max_cell_notional_usdt:
            violations.append(
                f"cell_notional({req_notional:.2f}) > max({self._limits.max_cell_notional_usdt:.2f})"
            )
        
        if new_count > self._limits.max_open_positions:
            violations.append(
                f"open_positions({new_count}) > max({self._limits.max_open_positions})"
            )
        
        # Determine decision
        if violations:
            if self._limits.enforce == "BLOCK":
                decision = RiskDecisionType.BLOCK
                allow = False
            else:
                decision = RiskDecisionType.WARN
                allow = True
        else:
            decision = RiskDecisionType.PASS
            allow = True
        
        reason = "; ".join(violations) if violations else "PASS"
        
        result = RiskDecision(
            allow=allow,
            decision=decision,
            cell_id=cell_id,
            cell_notional=req_notional,
            total_notional=new_total,
            open_positions_count=new_count,
            violations=violations,
            reason=reason,
            max_total_notional=self._limits.max_total_notional_usdt,
            max_cell_notional=self._limits.max_cell_notional_usdt,
            max_open_positions=self._limits.max_open_positions,
            enforce_mode=self._limits.enforce,
        )
        
        self._last_decision = result
        
        # Emit telemetry
        if self._event_sink:
            event_type = (
                "RISK_LIMIT_BLOCK" if decision == RiskDecisionType.BLOCK
                else "RISK_LIMIT_CHECK"
            )
            self._event_sink({
                "event_type": event_type,
                "ts": datetime.now(timezone.utc).isoformat(),
                "cell_id": cell_id,
                "symbol": ctx.get("symbol"),
                "timeframe": ctx.get("timeframe"),
                "profile_id": ctx.get("profile_id"),
                "cycle_idx": ctx.get("cycle_idx"),
                **result.to_dict(),
            })
        
        return result
    
    def get_snapshot(self) -> RiskSnapshot:
        """Get current risk snapshot for UI."""
        return self.compute_totals()
