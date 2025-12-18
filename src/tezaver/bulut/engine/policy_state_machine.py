# Tezaver Bulut - Policy State Machine v1
"""
Policy State Machine v1.
Manages the execution lifecycle (Open/Close) ensuring strict adherence to contracts:
- Closed Bar Only
- HOLD_NEXT_CLOSED logic (Effective on next bar)
- Min Hold Bars
- Dust Policy
- HTF Veto
"""

from typing import Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import time
import hashlib

from tezaver.bulut.core.config import BulutConfig
from tezaver.bulut.core.context import BulutContext


class PolicyPhase(str, Enum):
    IDLE = "IDLE"
    OPENING = "OPENING"         # Open submitted, waiting for effective
    EFFECTIVE = "EFFECTIVE"     # Open effectively (bars counting)
    CLOSING = "CLOSING"         # Close submitted


class PolicyDecision(str, Enum):
    ALLOW_OPEN = "ALLOW_OPEN"
    BLOCK_OPEN = "BLOCK_OPEN"
    ALLOW_CLOSE = "ALLOW_CLOSE"
    BLOCK_CLOSE = "BLOCK_CLOSE"
    NOOP = "NOOP"


@dataclass
class PolicyState:
    symbol: str
    phase: PolicyPhase = PolicyPhase.IDLE
    opened_cycle_ts: Optional[datetime] = None  # When OPEN was submitted
    effective_cycle_ts: Optional[datetime] = None # When it became effective (next closed bar)
    last_action_ts: Optional[datetime] = None
    hold_bars_remaining: int = 0
    last_reason: str = ""
    last_update_ms: int = 0  # OOO Protection

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "phase": self.phase.value,
            "opened_cycle_ts": self.opened_cycle_ts.isoformat() if self.opened_cycle_ts else None,
            "effective_cycle_ts": self.effective_cycle_ts.isoformat() if self.effective_cycle_ts else None,
            "last_action_ts": self.last_action_ts.isoformat() if self.last_action_ts else None,
            "hold_bars_remaining": self.hold_bars_remaining,
            "last_reason": self.last_reason,
            "last_update_ms": self.last_update_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PolicyState":
        def parse_ts(ts): 
            return datetime.fromisoformat(ts) if ts else None
            
        return cls(
            symbol=data.get("symbol", ""),
            phase=PolicyPhase(data.get("phase", "IDLE")),
            opened_cycle_ts=parse_ts(data.get("opened_cycle_ts")),
            effective_cycle_ts=parse_ts(data.get("effective_cycle_ts")),
            last_action_ts=parse_ts(data.get("last_action_ts")),
            hold_bars_remaining=int(data.get("hold_bars_remaining", 0)),
            last_reason=data.get("last_reason", ""),
            last_update_ms=int(data.get("last_update_ms", 0))
        )


class PolicyStateMachine:
    def __init__(self, config: BulutConfig):
        self._config = config
        # Load settings dynamically from config if possible or use provided
        self.min_hold_bars = getattr(config, "policy_min_hold_bars", 2)
        self.dust_policy = getattr(config, "policy_dust_policy", "FLATTEN_AFTER")
        self.htf_veto_enabled = getattr(config, "policy_htf_veto_enabled", True)

    def get_state(self, ctx: BulutContext, symbol: str) -> PolicyState:
        """Retrieve state from persistence or return new IDLE state."""
        raw = ctx.persistence.get_policy_state(symbol)
        if raw:
            return PolicyState.from_dict(raw)
        return PolicyState(symbol=symbol)

    def save_state(self, ctx: BulutContext, state: PolicyState):
        """Persist state with OOO protection."""
        # Update timestamp
        state.last_update_ms = int(time.time() * 1000)
        
        ctx.persistence.upsert_policy_state(state.to_dict())
        ctx.telemetry.emit("POLICY_STATE", {
            "symbol": state.symbol,
            "phase": state.phase.value,
            "hold_remaining": state.hold_bars_remaining,
            "update_ms": state.last_update_ms
        })

    def make_decision_id(self, symbol: str, cycle_ts: datetime, action: str, phase: str) -> str:
        """
        Create a deterministic Decision ID.
        Format: sha256(symbol|iso_ts|action|phase)[:16]
        """
        ts_str = cycle_ts.isoformat() if cycle_ts else "NO_TS"
        raw = f"{symbol}|{ts_str}|{action}|{phase}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def evaluate_open(
        self,
        ctx: BulutContext,
        symbol: str,
        cycle_ts: datetime,
        bar_is_closed: bool,
        htf_ok: bool,
        position_open: bool
    ) -> Tuple[PolicyDecision, str, str]:
        """
        Evaluate eligibility for OPEN.
        Returns: (Decision, Reason, DecisionID)
        """
        # C1: Closed Bar Only
        if not bar_is_closed:
            # We don't generate IDs for low-level blocks like "Bar Not Closed" usually, 
            # but for determinism if we log it, we might want one. 
            # However, usually we only ID "Active" decisions.
            # Let's return empty ID for trivial blocks? No, consistent ID is better.
            did = self.make_decision_id(symbol, cycle_ts, "OPEN_CHECK", "PrePhase")
            return PolicyDecision.BLOCK_OPEN, "BAR_NOT_CLOSED", did
        
        # HTF Veto
        did = self.make_decision_id(symbol, cycle_ts, "OPEN_CHECK", "HTF")
        if self.htf_veto_enabled and not htf_ok:
            return PolicyDecision.BLOCK_OPEN, "HTF_VETO", did

        # Check existing state
        state = self.get_state(ctx, symbol)
        
        # ID includes current phase
        did = self.make_decision_id(symbol, cycle_ts, "OPEN_CHECK", state.phase.value)
        
        # If position actually exists on exchange but state is IDLE -> State drift or manual/legacy trade.
        if position_open and state.phase == PolicyPhase.IDLE:
             return PolicyDecision.BLOCK_OPEN, "POSITION_EXISTS", did
             
        if state.phase != PolicyPhase.IDLE:
             return PolicyDecision.BLOCK_OPEN, f"PHASE_{state.phase.value}", did

        # Dust Check (Pre-Open)
        if position_open and self.dust_policy == "BLOCK":
             return PolicyDecision.BLOCK_OPEN, "DUST_RESIDUAL_BLOCK", did

        # Allowed
        return PolicyDecision.ALLOW_OPEN, "OK", did

    def transition_on_open_submit(self, ctx: BulutContext, symbol: str, cycle_ts: datetime):
        """Transition state when OPEN plan is generated/submitted."""
        state = self.get_state(ctx, symbol)
        state.phase = PolicyPhase.OPENING
        state.opened_cycle_ts = cycle_ts
        state.last_action_ts = datetime.now(timezone.utc)
        state.last_reason = "OPEN_SUBMITTED"
        # Reset hold bars to max initially? No, hold bars logic is computed at effective.
        # But we can store it for visibility.
        state.hold_bars_remaining = self.min_hold_bars
        self.save_state(ctx, state)

    def evaluate_close(
        self,
        ctx: BulutContext,
        symbol: str,
        cycle_ts: datetime,
        bar_is_closed: bool,
        position_open: bool,
        position_qty: float = 0.0,
        reduce_only: bool = True
    ) -> Tuple[PolicyDecision, str, str]:
        """
        Evaluate eligibility for CLOSE.
        Returns: (Decision, Reason, DecisionID)
        """
        did_base = self.make_decision_id(symbol, cycle_ts, "CLOSE_CHECK", "PrePhase")

        if not bar_is_closed:
            return PolicyDecision.BLOCK_CLOSE, "BAR_NOT_CLOSED", did_base
            
        state = self.get_state(ctx, symbol)
        
        # Update ID with actual phase
        did = self.make_decision_id(symbol, cycle_ts, "CLOSE_CHECK", state.phase.value)
        
        if state.phase == PolicyPhase.IDLE:
             return PolicyDecision.ALLOW_CLOSE, "OK_IDLE", did
        
        # Effective Transition
        if state.phase == PolicyPhase.OPENING:
             if state.opened_cycle_ts and cycle_ts > state.opened_cycle_ts:
                 state.phase = PolicyPhase.EFFECTIVE
                 state.effective_cycle_ts = cycle_ts
                 self.save_state(ctx, state)

        # Min Hold Bars (Deterministic Index)
        if state.opened_cycle_ts:
            # Assumes 15m intervals (900s). In production should come from config 'interval_seconds'.
            diff_seconds = (cycle_ts - state.opened_cycle_ts).total_seconds()
            bars_passed = int(diff_seconds // 900)
            
            remaining = max(0, self.min_hold_bars - bars_passed)
            
            # Sync visibility field
            if remaining != state.hold_bars_remaining:
                 state.hold_bars_remaining = remaining
                 self.save_state(ctx, state)

            if remaining > 0:
                return PolicyDecision.BLOCK_CLOSE, f"MIN_HOLD_NOT_MET ({remaining})", did

        # Dust Policy
        if position_open and position_qty > 0 and position_qty < 0.001: 
             if self.dust_policy == "FLATTEN_AFTER":
                 pass 
        
        return PolicyDecision.ALLOW_CLOSE, "OK", did

    def transition_on_close_submit(self, ctx: BulutContext, symbol: str):
        """Transition state when CLOSE plan is generated."""
        state = self.get_state(ctx, symbol)
        state.phase = PolicyPhase.CLOSING
        state.last_reason = "CLOSE_SUBMITTED"
        self.save_state(ctx, state)

    def reconcile_after_execution(self, ctx: BulutContext, symbol: str, position_closed: bool):
        """
        Called by Executor after trade finalization.
        If position is closed (qty=0), reset to IDLE.
        """
        state = self.get_state(ctx, symbol)
        if position_closed:
            state.phase = PolicyPhase.IDLE
            state.opened_cycle_ts = None
            state.effective_cycle_ts = None
            state.hold_bars_remaining = 0
            state.last_reason = "POSITION_CLOSED"
            self.save_state(ctx, state)

    def repair_state_drift(self, ctx: BulutContext):
        """
        Startup Check: Detect and fix Policy State Drift.
        Condition: Position OPEN, but Policy State IDLE.
        Action: Transition to EFFECTIVE (assume manual/legacy open).
        """
        open_positions = ctx.persistence.get_open_positions()
        if not open_positions:
            return
            
        for pos in open_positions:
            symbol = pos["symbol"]
            state = self.get_state(ctx, symbol)
            
            if state.phase == PolicyPhase.IDLE:
                # Drift Detected
                print(f"[POLICY] State Drift Detected for {symbol}: Position OPEN but State IDLE. Repairing...")
                
                # Assume EFFECTIVE (skipping opening/hold checks since we are already in)
                state.phase = PolicyPhase.EFFECTIVE
                # Use position entry time if available?
                entry_ts = datetime.fromisoformat(pos["entry_ts"]) if pos.get("entry_ts") else datetime.now(timezone.utc)
                state.opened_cycle_ts = entry_ts
                state.effective_cycle_ts = entry_ts
                state.last_reason = "REPAIR_DRIFT"
                state.hold_bars_remaining = 0 # Assume satisfied or reset
                
                self.save_state(ctx, state)
                ctx.telemetry.emit("DETERMINISM_REPAIR", {
                    "kind": "POLICY_DRIFT", 
                    "symbol": symbol, 
                    "action": "FORCE_EFFECTIVE"
                })
