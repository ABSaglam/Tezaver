# Tezaver Bulut - Performance & Cost Guard Service (P13)
"""
Performance and cost management with automatic degradation modes.
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


class PerfCostMode(Enum):
    """Performance cost guard operating modes."""
    NORMAL = "NORMAL"
    DEGRADED = "DEGRADED"
    EMERGENCY = "EMERGENCY"


@dataclass
class PerfCostRecommendations:
    """Recommended scanner parameters based on current load."""
    scan_topk: int  # Number of coins to scan
    poll_interval_ms: int  # Polling interval
    catchup_bars_max: int  # Max bars for catchup


@dataclass
class PerfCostStatus:
    """Current performance status."""
    mode: PerfCostMode
    cycle_avg_ms: float
    market_budget_used: float  # 0-1
    trade_budget_used: float  # 0-1
    recommendations: PerfCostRecommendations
    reasons: List[str]
    last_evaluated: str


class PerfCostGuardService:
    """
    Guards against performance and cost overruns.
    
    Monitors:
    - API budget usage (market/trade weights)
    - Cycle duration moving average
    - Scan duration
    
    Provides:
    - Operating mode (NORMAL/DEGRADED/EMERGENCY)
    - Dynamic parameter recommendations
    - Reasons for current state
    """
    
    # Thresholds
    BUDGET_WARN_THRESHOLD = 0.7  # 70% of budget
    BUDGET_DEGRADE_THRESHOLD = 0.85  # 85% triggers degraded
    BUDGET_EMERGENCY_THRESHOLD = 0.95  # 95% triggers emergency
    
    CYCLE_WARN_MS = 5000  # 5s warning
    CYCLE_DEGRADE_MS = 10000  # 10s degraded
    CYCLE_EMERGENCY_MS = 30000  # 30s emergency
    
    # Default parameters
    DEFAULTS = {
        "normal": PerfCostRecommendations(scan_topk=50, poll_interval_ms=60000, catchup_bars_max=100),
        "degraded": PerfCostRecommendations(scan_topk=20, poll_interval_ms=120000, catchup_bars_max=50),
        "emergency": PerfCostRecommendations(scan_topk=10, poll_interval_ms=300000, catchup_bars_max=20),
    }
    
    def __init__(self, ctx):
        self._ctx = ctx
        self._mode: PerfCostMode = PerfCostMode.NORMAL
        self._cycle_times: List[float] = []
        self._max_history = 20
        self._force_mode: Optional[PerfCostMode] = None
        self._last_evaluated: Optional[str] = None
        self._current_reasons: List[str] = []
    
    def record_cycle(self, duration_ms: float):
        """Record a cycle duration for moving average."""
        self._cycle_times.append(duration_ms)
        if len(self._cycle_times) > self._max_history:
            self._cycle_times = self._cycle_times[-self._max_history:]
    
    def get_cycle_avg_ms(self) -> float:
        """Get cycle duration moving average."""
        if not self._cycle_times:
            return 0.0
        return sum(self._cycle_times) / len(self._cycle_times)
    
    def evaluate(self) -> PerfCostStatus:
        """
        Evaluate current state and determine mode.
        
        Returns status with mode, reasons, and recommendations.
        """
        reasons = []
        suggested_mode = PerfCostMode.NORMAL
        
        # Get budget usage from governor
        market_budget = 0.0
        trade_budget = 0.0
        try:
            governor = self._ctx.governor
            if governor:
                market_budget = governor.get_market_usage_ratio()
                trade_budget = governor.get_trade_usage_ratio()
        except Exception:
            pass
        
        # Check budget thresholds
        max_budget = max(market_budget, trade_budget)
        if max_budget >= self.BUDGET_EMERGENCY_THRESHOLD:
            suggested_mode = PerfCostMode.EMERGENCY
            reasons.append(f"API budget critical: {max_budget:.0%}")
        elif max_budget >= self.BUDGET_DEGRADE_THRESHOLD:
            if suggested_mode != PerfCostMode.EMERGENCY:
                suggested_mode = PerfCostMode.DEGRADED
            reasons.append(f"API budget high: {max_budget:.0%}")
        elif max_budget >= self.BUDGET_WARN_THRESHOLD:
            reasons.append(f"API budget warning: {max_budget:.0%}")
        
        # Check cycle duration
        cycle_avg = self.get_cycle_avg_ms()
        if cycle_avg >= self.CYCLE_EMERGENCY_MS:
            suggested_mode = PerfCostMode.EMERGENCY
            reasons.append(f"Cycle time critical: {cycle_avg:.0f}ms")
        elif cycle_avg >= self.CYCLE_DEGRADE_MS:
            if suggested_mode != PerfCostMode.EMERGENCY:
                suggested_mode = PerfCostMode.DEGRADED
            reasons.append(f"Cycle time high: {cycle_avg:.0f}ms")
        elif cycle_avg >= self.CYCLE_WARN_MS:
            reasons.append(f"Cycle time warning: {cycle_avg:.0f}ms")
        
        # Apply forced mode if set
        if self._force_mode is not None:
            suggested_mode = self._force_mode
            reasons.append(f"Mode forced by operator")
        
        # Update state
        self._mode = suggested_mode
        self._current_reasons = reasons
        self._last_evaluated = datetime.now(timezone.utc).isoformat()
        
        # Get recommendations
        recommendations = self._get_recommendations(suggested_mode)
        
        # Save snapshot
        self._save_snapshot(market_budget, trade_budget, cycle_avg)
        
        # Emit telemetry
        self._emit_telemetry(market_budget, trade_budget, cycle_avg)
        
        return PerfCostStatus(
            mode=self._mode,
            cycle_avg_ms=cycle_avg,
            market_budget_used=market_budget,
            trade_budget_used=trade_budget,
            recommendations=recommendations,
            reasons=reasons,
            last_evaluated=self._last_evaluated
        )
    
    def _get_recommendations(self, mode: PerfCostMode) -> PerfCostRecommendations:
        """Get parameter recommendations for mode."""
        if mode == PerfCostMode.EMERGENCY:
            return self.DEFAULTS["emergency"]
        elif mode == PerfCostMode.DEGRADED:
            return self.DEFAULTS["degraded"]
        return self.DEFAULTS["normal"]
    
    def force_mode(self, mode: PerfCostMode, reason: str = "Operator override") -> bool:
        """Force a specific mode (ops command)."""
        self._force_mode = mode
        self._mode = mode
        self._current_reasons = [reason]
        self._last_evaluated = datetime.now(timezone.utc).isoformat()
        return True
    
    def clear_force(self) -> bool:
        """Clear forced mode, return to automatic."""
        self._force_mode = None
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status as dict."""
        recommendations = self._get_recommendations(self._mode)
        return {
            "mode": self._mode.value,
            "cycle_avg_ms": self.get_cycle_avg_ms(),
            "market_budget_used": self._get_market_budget(),
            "trade_budget_used": self._get_trade_budget(),
            "recommendations": {
                "scan_topk": recommendations.scan_topk,
                "poll_interval_ms": recommendations.poll_interval_ms,
                "catchup_bars_max": recommendations.catchup_bars_max
            },
            "reasons": self._current_reasons,
            "force_mode_active": self._force_mode is not None,
            "last_evaluated": self._last_evaluated
        }
    
    def _get_market_budget(self) -> float:
        """Get current market budget usage."""
        try:
            governor = self._ctx.governor
            if governor:
                return governor.get_market_usage_ratio()
        except Exception:
            pass
        return 0.0
    
    def _get_trade_budget(self) -> float:
        """Get current trade budget usage."""
        try:
            governor = self._ctx.governor
            if governor:
                return governor.get_trade_usage_ratio()
        except Exception:
            pass
        return 0.0
    
    def _save_snapshot(self, market_budget: float, trade_budget: float, cycle_avg: float):
        """Save performance snapshot to persistence."""
        try:
            import json
            self._ctx.persistence.save_perf_cost_snapshot({
                "ts": datetime.now(timezone.utc).isoformat(),
                "mode": self._mode.value,
                "metrics_json": json.dumps({
                    "market_budget": market_budget,
                    "trade_budget": trade_budget,
                    "cycle_avg_ms": cycle_avg,
                    "reasons": self._current_reasons
                })
            })
        except Exception:
            pass
    
    def _emit_telemetry(self, market_budget: float, trade_budget: float, cycle_avg: float):
        """Emit telemetry event."""
        try:
            self._ctx.telemetry.emit("PERF_COST_STATUS", {
                "mode": self._mode.value,
                "market_budget": market_budget,
                "trade_budget": trade_budget,
                "cycle_avg_ms": cycle_avg
            })
        except Exception:
            pass
    
    def get_overrides(self) -> Dict[str, Any]:
        """Get current parameter overrides for scheduler."""
        recommendations = self._get_recommendations(self._mode)
        return {
            "SCAN_TOPK": recommendations.scan_topk,
            "POLL_INTERVAL": recommendations.poll_interval_ms,
            "CATCHUP_MAX_BARS": recommendations.catchup_bars_max,
            "mode": self._mode.value
        }
