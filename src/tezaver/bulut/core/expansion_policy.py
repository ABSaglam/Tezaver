# Tezaver Bulut - Expansion Policy Service (P6)
"""
Manages tiered expansion limits for mainnet safe growth.
Tiers: T0=50, T1=200, T2=500 USDT per 24h window.
"""
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, List, Optional
from enum import IntEnum


class ExpansionTier(IntEnum):
    """Expansion tier levels."""
    T0_PILOT = 0      # 50 USDT
    T1_GROWTH = 1     # 200 USDT
    T2_SCALED = 2     # 500 USDT


# Default tier limits
TIER_LIMITS = {
    ExpansionTier.T0_PILOT: 50.0,
    ExpansionTier.T1_GROWTH: 200.0,
    ExpansionTier.T2_SCALED: 500.0,
}

# Required proof ladder steps for each tier
TIER_PROOF_REQUIREMENTS = {
    ExpansionTier.T1_GROWTH: 3,
    ExpansionTier.T2_SCALED: 4,
}


class ExpansionBlockReason:
    """Reasons for blocking tier step-up."""
    PROOF_INSUFFICIENT = "proof_ladder_insufficient"
    NET_PNL_NEGATIVE = "net_pnl_negative"
    CRITICAL_ALERTS = "critical_alerts_present"
    CONSTITUTION_FAIL = "constitution_guard_failed"
    STRICT_TIMING_UNHEALTHY = "strict_timing_unhealthy"
    ALREADY_MAX_TIER = "already_at_max_tier"
    EXPANSION_DISABLED = "expansion_disabled"


class ExpansionPolicyService:
    """
    Manages safe expansion from pilot to scaled mainnet trading.
    
    Step-up requires:
    - Proof Ladder >= required step for target tier
    - Net PnL >= 0 in last 24h
    - No critical alerts
    - Constitution/StrictTiming healthy
    """
    
    def __init__(self, ctx):
        self._ctx = ctx
        self._tier_limits = TIER_LIMITS.copy()
    
    def _load_state(self) -> Dict:
        """Load expansion state from persistence."""
        state = self._ctx.persistence.get_expansion_state()
        if not state:
            return {
                "current_tier": ExpansionTier.T0_PILOT.value,
                "tier_changed_ts": None,
                "tier_history": []
            }
        return state
    
    def _save_state(self, state: Dict):
        """Save expansion state to persistence."""
        self._ctx.persistence.update_expansion_state(state)
    
    def get_current_tier(self) -> ExpansionTier:
        """Get current expansion tier."""
        state = self._load_state()
        return ExpansionTier(state.get("current_tier", 0))
    
    def get_tier_limit(self) -> float:
        """Get current tier's USDT limit."""
        tier = self.get_current_tier()
        return self._tier_limits.get(tier, 50.0)
    
    def get_status(self) -> Dict[str, Any]:
        """Get expansion status."""
        state = self._load_state()
        tier = self.get_current_tier()
        can_step, reasons = self.can_step_up()
        
        return {
            "enabled": getattr(self._ctx.config, "expansion_enabled", True),
            "current_tier": tier.value,
            "current_tier_name": tier.name,
            "limit_usdt": self.get_tier_limit(),
            "max_tier": ExpansionTier.T2_SCALED.value,
            "can_step_up": can_step,
            "block_reasons": reasons,
            "tier_changed_ts": state.get("tier_changed_ts"),
            "tier_history": state.get("tier_history", [])[-10:]
        }
    
    def can_step_up(self) -> Tuple[bool, List[str]]:
        """
        Check if tier can be increased.
        
        Returns (allowed, list_of_block_reasons).
        """
        reasons = []
        config = self._ctx.config
        
        # Check if expansion enabled
        if not getattr(config, "expansion_enabled", True):
            return False, [ExpansionBlockReason.EXPANSION_DISABLED]
        
        # Check if already at max tier
        current_tier = self.get_current_tier()
        if current_tier >= ExpansionTier.T2_SCALED:
            return False, [ExpansionBlockReason.ALREADY_MAX_TIER]
        
        target_tier = ExpansionTier(current_tier.value + 1)
        
        # 1. Check Proof Ladder
        required_step = TIER_PROOF_REQUIREMENTS.get(target_tier, 0)
        try:
            ladder = self._ctx.proof_ladder
            if hasattr(ladder, 'current_step'):
                if ladder.current_step < required_step:
                    reasons.append(ExpansionBlockReason.PROOF_INSUFFICIENT)
        except Exception:
            reasons.append(ExpansionBlockReason.PROOF_INSUFFICIENT)
        
        # 2. Check Net PnL (last 24h)
        min_pnl = getattr(config, "expansion_min_net_pnl_for_stepup", 0.0)
        try:
            # Get net PnL from income service or persistence
            net_pnl = self._get_24h_net_pnl()
            if net_pnl < min_pnl:
                reasons.append(ExpansionBlockReason.NET_PNL_NEGATIVE)
        except Exception:
            pass  # Allow if can't check
        
        # 3. Check Critical Alerts
        block_on_alerts = getattr(config, "expansion_block_if_critical_alerts", True)
        if block_on_alerts:
            try:
                has_critical = self._has_critical_alerts()
                if has_critical:
                    reasons.append(ExpansionBlockReason.CRITICAL_ALERTS)
            except Exception:
                pass
        
        # 4. Check Constitution Guard
        try:
            guard = self._ctx.constitution_guard
            if hasattr(guard, 'is_compliant'):
                if not guard.is_compliant():
                    reasons.append(ExpansionBlockReason.CONSTITUTION_FAIL)
        except Exception:
            pass
        
        # 5. Check Strict Timing
        try:
            strict = self._ctx.strict_timing
            if hasattr(strict, 'is_healthy'):
                if not strict.is_healthy():
                    reasons.append(ExpansionBlockReason.STRICT_TIMING_UNHEALTHY)
        except Exception:
            pass
        
        return len(reasons) == 0, reasons
    
    def step_up(self) -> Tuple[bool, Optional[str]]:
        """
        Attempt to step up to next tier.
        
        Returns (success, error_message).
        """
        can, reasons = self.can_step_up()
        if not can:
            return False, f"Blocked: {', '.join(reasons)}"
        
        current_tier = self.get_current_tier()
        new_tier = ExpansionTier(current_tier.value + 1)
        
        state = self._load_state()
        now = datetime.now(timezone.utc).isoformat()
        
        # Update state
        state["current_tier"] = new_tier.value
        state["tier_changed_ts"] = now
        
        # Add to history
        history = state.get("tier_history", [])
        history.append({
            "from_tier": current_tier.value,
            "to_tier": new_tier.value,
            "ts": now
        })
        state["tier_history"] = history[-50:]  # Keep last 50
        
        self._save_state(state)
        
        # Emit telemetry
        try:
            self._ctx.telemetry.emit({
                "event": "EXPANSION_STEP_UP",
                "from_tier": current_tier.value,
                "to_tier": new_tier.value,
                "new_limit_usdt": self._tier_limits[new_tier]
            })
        except Exception:
            pass
        
        return True, None
    
    def set_tier(self, tier_index: int) -> Tuple[bool, Optional[str]]:
        """
        Forcefully set tier (ops override).
        
        Returns (success, error_message).
        """
        try:
            new_tier = ExpansionTier(tier_index)
        except ValueError:
            return False, f"Invalid tier index: {tier_index}"
        
        current_tier = self.get_current_tier()
        state = self._load_state()
        now = datetime.now(timezone.utc).isoformat()
        
        state["current_tier"] = new_tier.value
        state["tier_changed_ts"] = now
        
        history = state.get("tier_history", [])
        history.append({
            "from_tier": current_tier.value,
            "to_tier": new_tier.value,
            "ts": now,
            "forced": True
        })
        state["tier_history"] = history[-50:]
        
        self._save_state(state)
        
        try:
            self._ctx.telemetry.emit({
                "event": "EXPANSION_TIER_SET",
                "from_tier": current_tier.value,
                "to_tier": new_tier.value,
                "forced": True
            })
        except Exception:
            pass
        
        return True, None
    
    def _get_24h_net_pnl(self) -> float:
        """Get net PnL for last 24 hours."""
        try:
            # Use income service if available
            income = self._ctx.income_service
            if hasattr(income, 'get_24h_net_pnl'):
                return income.get_24h_net_pnl()
        except Exception:
            pass
        return 0.0  # Default to 0 if can't determine
    
    def _has_critical_alerts(self) -> bool:
        """Check for critical (sev-1) alerts in last 24h."""
        try:
            alerts = self._ctx.persistence.get_recent_alerts(hours=24)
            for alert in alerts:
                if alert.get("severity") == 1 or alert.get("level") == "BLOCK":
                    return True
        except Exception:
            pass
        return False
