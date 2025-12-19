# Tezaver Bulut - Allocation Engine (P7)
"""
Capital allocation engine for per-symbol and per-pattern budget management.
Ensures trading stays within tier limits with granular budget control.
"""
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class AllocationDenyReason(Enum):
    """Reasons for denying allocation."""
    SYMBOL_BUDGET_EXCEEDED = "symbol_budget_exceeded"
    PATTERN_BUDGET_EXCEEDED = "pattern_budget_exceeded"
    TIER_BUDGET_EXCEEDED = "tier_budget_exceeded"
    GROUP_BUDGET_EXCEEDED = "group_budget_exceeded"


@dataclass
class AllocationDecision:
    """Result of allocation check."""
    symbol: str
    pattern: Optional[str]
    notional_usdt: float
    allowed: bool
    deny_reason: Optional[str]
    symbol_usage_pct: float
    pattern_usage_pct: float
    tier_usage_pct: float
    timestamp: str


class AllocationEngine:
    """
    Capital Allocation Engine for budget management.
    
    Two-layer budgeting:
    1. Tier limit (from ExpansionPolicy): 50/200/500 USDT
    2. Per-symbol and per-pattern percentage caps
    
    Default caps:
    - max_symbol_pct_of_tier: 10% (symbol can use up to 10% of tier limit)
    - max_pattern_pct_of_tier: 5% (pattern can use up to 5%)
    """
    
    # Default allocation percentages
    DEFAULT_MAX_SYMBOL_PCT = 10.0
    DEFAULT_MAX_PATTERN_PCT = 5.0
    
    def __init__(self, ctx):
        self._ctx = ctx
        self._symbol_usage: Dict[str, float] = {}  # symbol -> committed USDT
        self._pattern_usage: Dict[str, float] = {}  # pattern -> committed USDT
        self._decisions: List[AllocationDecision] = []
        self._overrides = self._load_overrides()
    
    def _load_overrides(self) -> Dict:
        """Load allocation overrides from config/rules."""
        overrides = {
            "symbol": {},  # e.g., {"BTCUSDT": 15.0}
            "pattern": {}  # e.g., {"SILVER_BULL": 8.0}
        }
        
        # Try to load from config or persistence
        try:
            config = self._ctx.config
            if hasattr(config, 'allocation_symbol_overrides'):
                overrides["symbol"] = config.allocation_symbol_overrides or {}
            if hasattr(config, 'allocation_pattern_overrides'):
                overrides["pattern"] = config.allocation_pattern_overrides or {}
        except Exception:
            pass
        
        return overrides
    
    def _get_tier_limit(self) -> float:
        """Get current tier limit from expansion policy."""
        try:
            return self._ctx.expansion_policy.get_tier_limit()
        except Exception:
            return 50.0  # Default pilot limit
    
    def _get_symbol_max_pct(self, symbol: str) -> float:
        """Get max percentage for symbol (with overrides)."""
        return self._overrides["symbol"].get(symbol, self.DEFAULT_MAX_SYMBOL_PCT)
    
    def _get_pattern_max_pct(self, pattern: str) -> float:
        """Get max percentage for pattern (with overrides)."""
        return self._overrides["pattern"].get(pattern, self.DEFAULT_MAX_PATTERN_PCT)
    
    def _get_current_usage(self) -> Dict:
        """Get current budget usage from persistence."""
        try:
            state = self._ctx.persistence.get_allocation_state()
            if state:
                self._symbol_usage = state.get("symbol_usage", {})
                self._pattern_usage = state.get("pattern_usage", {})
        except Exception:
            pass
        
        return {
            "symbol": self._symbol_usage.copy(),
            "pattern": self._pattern_usage.copy()
        }
    
    def _save_usage(self):
        """Save current usage to persistence."""
        try:
            state = {
                "symbol_usage": self._symbol_usage,
                "pattern_usage": self._pattern_usage,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            self._ctx.persistence.update_allocation_state(state)
        except Exception:
            pass
    
    def check_allocation(
        self, 
        symbol: str, 
        pattern: Optional[str], 
        notional_usdt: float
    ) -> AllocationDecision:
        """
        Check if allocation is allowed for a trading decision.
        
        Returns AllocationDecision with allowed status and usage percentages.
        """
        self._get_current_usage()
        tier_limit = self._get_tier_limit()
        now = datetime.now(timezone.utc).isoformat()
        
        # Calculate current usage
        current_symbol_usage = self._symbol_usage.get(symbol, 0.0)
        current_pattern_usage = self._pattern_usage.get(pattern, 0.0) if pattern else 0.0
        total_usage = sum(self._symbol_usage.values())
        
        # Calculate new usage if allowed
        new_symbol_usage = current_symbol_usage + notional_usdt
        new_pattern_usage = current_pattern_usage + notional_usdt if pattern else 0.0
        new_total_usage = total_usage + notional_usdt
        
        # Calculate percentages
        symbol_usage_pct = (new_symbol_usage / tier_limit) * 100 if tier_limit > 0 else 0
        pattern_usage_pct = (new_pattern_usage / tier_limit) * 100 if tier_limit > 0 and pattern else 0
        tier_usage_pct = (new_total_usage / tier_limit) * 100 if tier_limit > 0 else 0
        
        # Get limits
        symbol_max_pct = self._get_symbol_max_pct(symbol)
        pattern_max_pct = self._get_pattern_max_pct(pattern) if pattern else 100.0
        
        # Check limits
        deny_reason = None
        allowed = True
        
        if tier_usage_pct > 100:
            allowed = False
            deny_reason = AllocationDenyReason.TIER_BUDGET_EXCEEDED.value
        elif symbol_usage_pct > symbol_max_pct:
            allowed = False
            deny_reason = AllocationDenyReason.SYMBOL_BUDGET_EXCEEDED.value
        elif pattern and pattern_usage_pct > pattern_max_pct:
            allowed = False
            deny_reason = AllocationDenyReason.PATTERN_BUDGET_EXCEEDED.value
        
        decision = AllocationDecision(
            symbol=symbol,
            pattern=pattern,
            notional_usdt=notional_usdt,
            allowed=allowed,
            deny_reason=deny_reason,
            symbol_usage_pct=round(symbol_usage_pct, 2),
            pattern_usage_pct=round(pattern_usage_pct, 2),
            tier_usage_pct=round(tier_usage_pct, 2),
            timestamp=now
        )
        
        # Record decision
        self._decisions.append(decision)
        if len(self._decisions) > 1000:
            self._decisions = self._decisions[-500:]
        
        # Emit telemetry
        try:
            self._ctx.telemetry.emit({
                "event": "ALLOCATION_CHECK",
                "symbol": symbol,
                "pattern": pattern,
                "notional_usdt": notional_usdt,
                "allowed": allowed,
                "deny_reason": deny_reason,
                "symbol_usage_pct": decision.symbol_usage_pct,
                "tier_usage_pct": decision.tier_usage_pct
            })
        except Exception:
            pass
        
        return decision
    
    def commit_allocation(
        self, 
        symbol: str, 
        pattern: Optional[str], 
        notional_usdt: float
    ):
        """Commit allocation after trade is executed."""
        self._get_current_usage()
        
        self._symbol_usage[symbol] = self._symbol_usage.get(symbol, 0.0) + notional_usdt
        if pattern:
            self._pattern_usage[pattern] = self._pattern_usage.get(pattern, 0.0) + notional_usdt
        
        self._save_usage()
    
    def release_allocation(
        self, 
        symbol: str, 
        pattern: Optional[str], 
        notional_usdt: float
    ):
        """Release allocation when position is closed."""
        self._get_current_usage()
        
        self._symbol_usage[symbol] = max(0, self._symbol_usage.get(symbol, 0.0) - notional_usdt)
        if pattern:
            self._pattern_usage[pattern] = max(0, self._pattern_usage.get(pattern, 0.0) - notional_usdt)
        
        self._save_usage()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current allocation status."""
        self._get_current_usage()
        tier_limit = self._get_tier_limit()
        total_used = sum(self._symbol_usage.values())
        
        return {
            "tier_limit_usdt": tier_limit,
            "total_used_usdt": total_used,
            "remaining_usdt": max(0, tier_limit - total_used),
            "tier_usage_pct": round((total_used / tier_limit) * 100, 2) if tier_limit > 0 else 0,
            "symbol_usage": {k: round(v, 2) for k, v in self._symbol_usage.items()},
            "pattern_usage": {k: round(v, 2) for k, v in self._pattern_usage.items()},
            "symbol_overrides": self._overrides["symbol"],
            "pattern_overrides": self._overrides["pattern"],
            "default_symbol_max_pct": self.DEFAULT_MAX_SYMBOL_PCT,
            "default_pattern_max_pct": self.DEFAULT_MAX_PATTERN_PCT
        }
    
    def get_decisions(self, limit: int = 100) -> List[Dict]:
        """Get recent allocation decisions."""
        decisions = self._decisions[-limit:]
        return [
            {
                "symbol": d.symbol,
                "pattern": d.pattern,
                "notional_usdt": d.notional_usdt,
                "allowed": d.allowed,
                "deny_reason": d.deny_reason,
                "symbol_usage_pct": d.symbol_usage_pct,
                "pattern_usage_pct": d.pattern_usage_pct,
                "tier_usage_pct": d.tier_usage_pct,
                "timestamp": d.timestamp
            }
            for d in reversed(decisions)
        ]
    
    def reset(self):
        """Reset all allocations (for testing or new period)."""
        self._symbol_usage = {}
        self._pattern_usage = {}
        self._decisions = []
        self._save_usage()
