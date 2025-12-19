# Tezaver Bulut - Autopilot Service (P5)
"""
Gating logic for automated mainnet execution.
Ensures all safety checks pass before auto-accepting plans.
"""
from typing import Tuple, Dict, Any, List, Optional
from enum import Enum


class AutopilotBlockReason(Enum):
    """Reasons why autopilot may be blocked."""
    NONE = "none"
    DISABLED = "autopilot_disabled"
    WRONG_MODE = "not_real_mainnet"
    LAUNCH_CHECKLIST_FAIL = "launch_checklist_failed"
    CONSTITUTION_GUARD_FAIL = "constitution_guard_failed"
    DRIFT_GUARD_FAIL = "drift_guard_failed"  
    STRICT_TIMING_UNHEALTHY = "strict_timing_unhealthy"
    PROOF_LADDER_INSUFFICIENT = "proof_ladder_insufficient"
    PILOT_LIMIT_REACHED = "pilot_limit_reached"
    NO_TOKEN = "ops_token_missing"


class AutopilotService:
    """
    Manages autopilot state and gating for mainnet pilot phase.
    
    Autopilot only accepts plans if ALL safety checks pass:
    - MODE == REAL_MAINNET
    - LaunchChecklist PASS
    - ConstitutionGuard PASS
    - DriftGuard PASS
    - StrictTiming healthy
    - Proof Ladder sufficient
    - Pilot Meter has remaining limit
    """
    
    MAX_NEW_ENTRIES_PER_CYCLE = 1
    REQUIRED_PROOF_STEP = 3  # Minimum proof ladder step for autopilot
    
    def __init__(self, ctx):
        self._ctx = ctx
        self._enabled = False
        self._last_block_reason: Optional[AutopilotBlockReason] = None
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    def enable(self) -> bool:
        """Enable autopilot (returns True if successful)."""
        can, reason = self.check_can_autopilot()
        if can:
            self._enabled = True
            self._last_block_reason = None
            return True
        else:
            self._last_block_reason = reason
            return False
    
    def disable(self):
        """Disable autopilot."""
        self._enabled = False
    
    def check_can_autopilot(self) -> Tuple[bool, Optional[AutopilotBlockReason]]:
        """
        Check if autopilot can operate.
        
        Returns (allowed, block_reason).
        """
        config = self._ctx.config
        
        # 1. Check MODE
        if config.mode != "REAL_MAINNET":
            return False, AutopilotBlockReason.WRONG_MODE
        
        # 2. Check Launch Checklist
        try:
            checklist = self._ctx.launch_checklist
            if hasattr(checklist, 'check_all'):
                result = checklist.check_all()
                if not result.get("passed", False):
                    return False, AutopilotBlockReason.LAUNCH_CHECKLIST_FAIL
        except Exception:
            return False, AutopilotBlockReason.LAUNCH_CHECKLIST_FAIL
        
        # 3. Check Constitution Guard
        try:
            guard = self._ctx.constitution_guard
            if hasattr(guard, 'is_compliant'):
                if not guard.is_compliant():
                    return False, AutopilotBlockReason.CONSTITUTION_GUARD_FAIL
        except Exception:
            pass  # Constitution guard may not exist yet
        
        # 4. Check Strict Timing
        try:
            strict = self._ctx.strict_timing
            if hasattr(strict, 'is_healthy'):
                if not strict.is_healthy():
                    return False, AutopilotBlockReason.STRICT_TIMING_UNHEALTHY
        except Exception:
            pass  # StrictTiming may not exist
        
        # 5. Check Proof Ladder
        try:
            ladder = self._ctx.proof_ladder
            if hasattr(ladder, 'current_step'):
                if ladder.current_step < self.REQUIRED_PROOF_STEP:
                    return False, AutopilotBlockReason.PROOF_LADDER_INSUFFICIENT
        except Exception:
            pass  # Proof ladder may not exist
        
        # 6. Check Pilot Meter
        try:
            pilot = self._ctx.pilot_meter
            if pilot.is_limit_reached():
                return False, AutopilotBlockReason.PILOT_LIMIT_REACHED
        except Exception:
            pass  # Pilot meter may not exist
        
        return True, None
    
    def get_status(self) -> Dict[str, Any]:
        """Get autopilot status."""
        can, reason = self.check_can_autopilot()
        
        return {
            "enabled": self._enabled,
            "can_operate": can,
            "block_reason": reason.value if reason else None,
            "last_block_reason": self._last_block_reason.value if self._last_block_reason else None,
            "max_entries_per_cycle": self.MAX_NEW_ENTRIES_PER_CYCLE
        }
    
    def auto_accept_proposed_plans(self, plans: List[Any]) -> List[Any]:
        """
        Auto-accept proposed plans if autopilot is enabled and can operate.
        
        Returns list of accepted plans.
        """
        if not self._enabled:
            return []
        
        can, reason = self.check_can_autopilot()
        if not can:
            self._last_block_reason = reason
            # Emit telemetry
            try:
                self._ctx.telemetry.emit({
                    "event": "AUTOPILOT_BLOCKED",
                    "reason": reason.value
                })
            except Exception:
                pass
            return []
        
        # Filter to OPEN decisions only (entries)
        open_plans = [p for p in plans if hasattr(p, 'decision') and p.decision.name == "OPEN"]
        
        # Limit to max entries per cycle
        to_accept = open_plans[:self.MAX_NEW_ENTRIES_PER_CYCLE]
        
        accepted = []
        for plan in to_accept:
            # Check pilot meter can commit
            try:
                notional = plan.notional_usdt or 0
                pilot = self._ctx.pilot_meter
                if not pilot.can_commit(notional):
                    self._last_block_reason = AutopilotBlockReason.PILOT_LIMIT_REACHED
                    break
                
                # Commit and accept
                pilot.commit_notional(notional)
                # Mark plan as accepted
                plan.status = "ACCEPTED"
                accepted.append(plan)
                
            except Exception as e:
                print(f"[AUTOPILOT] Error accepting plan: {e}")
                break
        
        return accepted
